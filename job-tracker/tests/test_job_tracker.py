# job-tracker/tests/test_job_tracker.py
import sqlite3
from datetime import timedelta

import pytest

import job_tracker


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "applications.db"


def _rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT company, role, date_applied, status, referral_contact, last_updated FROM applications"
    ).fetchall()
    conn.close()
    return rows


def _add(db_path, company, role, date_applied, status="Applied", referral=""):
    args = [
        "add", "--company", company, "--role", role,
        "--date-applied", date_applied, "--status", status,
    ]
    if referral:
        args += ["--referral", referral]
    job_tracker.main(args, db_path=db_path)


def _add_with_last_updated(db_path, company, role, status, last_updated):
    conn = job_tracker.get_connection(db_path)
    conn.execute(
        "INSERT INTO applications (company, role, date_applied, status, referral_contact, last_updated) "
        "VALUES (?, ?, ?, ?, '', ?)",
        (company, role, last_updated, status, last_updated),
    )
    conn.commit()
    conn.close()


def test_add_creates_application_with_all_fields(db_path):
    """Adding an application stores company, role, date, status, and referral."""
    exit_code = job_tracker.main(
        [
            "add",
            "--company", "Acme Corp",
            "--role", "Backend Engineer",
            "--date-applied", "2026-07-01",
            "--status", "Applied",
            "--referral", "Jane Doe",
        ],
        db_path=db_path,
    )
    assert exit_code == 0
    rows = _rows(db_path)
    assert rows == [("Acme Corp", "Backend Engineer", "2026-07-01", "Applied", "Jane Doe", "2026-07-01")]


def test_add_without_referral_defaults_empty(db_path):
    """Omitting --referral stores an empty string, not null or a missing row."""
    job_tracker.main(
        [
            "add",
            "--company", "Beta Inc",
            "--role", "Data Analyst",
            "--date-applied", "2026-07-15",
            "--status", "Applied",
        ],
        db_path=db_path,
    )
    rows = _rows(db_path)
    assert rows[0][4] == ""


def test_add_new_application_last_updated_equals_date_applied(db_path):
    """A freshly added application's last_updated starts equal to its date_applied."""
    job_tracker.main(
        [
            "add",
            "--company", "Acme Corp",
            "--role", "Backend Engineer",
            "--date-applied", "2026-07-01",
            "--status", "Applied",
        ],
        db_path=db_path,
    )
    rows = _rows(db_path)
    assert rows[0][2] == rows[0][5] == "2026-07-01"


def test_add_normalizes_status_case(db_path):
    """Status is matched case-insensitively and stored in its canonical form."""
    job_tracker.main(
        [
            "add",
            "--company", "Acme Corp",
            "--role", "Backend Engineer",
            "--date-applied", "2026-07-01",
            "--status", "applied",
        ],
        db_path=db_path,
    )
    rows = _rows(db_path)
    assert rows[0][3] == "Applied"


def test_add_rejects_invalid_status(db_path, capsys):
    """An unrecognized status is rejected with a stderr message, exit 1, and no write."""
    exit_code = job_tracker.main(
        [
            "add",
            "--company", "Acme Corp",
            "--role", "Backend Engineer",
            "--date-applied", "2026-07-01",
            "--status", "Interviewing Round 2",
        ],
        db_path=db_path,
    )
    assert exit_code == 1
    assert "invalid status" in capsys.readouterr().err
    assert _rows(db_path) == []


def test_add_assigns_unique_incrementing_ids(db_path):
    """Each added application gets a distinct id assigned by the tool."""
    for i in range(2):
        job_tracker.main(
            [
                "add",
                "--company", f"Company {i}",
                "--role", "Engineer",
                "--date-applied", "2026-07-01",
                "--status", "Applied",
            ],
            db_path=db_path,
        )
    conn = sqlite3.connect(db_path)
    ids = [r[0] for r in conn.execute("SELECT id FROM applications ORDER BY id")]
    conn.close()
    assert ids == [1, 2]


def test_list_sorted_by_date_applied_desc_with_all_columns(db_path, capsys):
    """List shows every application, most recently applied first, with all fields."""
    _add(db_path, "Old Co", "Engineer", "2026-06-01")
    _add(db_path, "New Co", "Engineer", "2026-07-15", referral="Jane Doe")
    _add(db_path, "Mid Co", "Engineer", "2026-07-01")
    capsys.readouterr()

    exit_code = job_tracker.main(["list"], db_path=db_path)

    assert exit_code == 0
    output = capsys.readouterr().out
    companies_in_order = [line.split()[1] for line in output.splitlines()[2:]]
    assert companies_in_order == ["New", "Mid", "Old"]
    assert "Jane Doe" in output
    assert "ID" in output and "Last Updated" in output


def test_update_changes_status_and_last_updated(db_path):
    """Updating by company/role changes status and stamps last_updated with today."""
    _add(db_path, "Acme Corp", "Backend Engineer", "2026-07-01")

    exit_code = job_tracker.main(
        ["update", "--company", "Acme Corp", "--role", "Backend Engineer", "--status", "Interviewing"],
        db_path=db_path,
    )

    assert exit_code == 0
    row = _rows(db_path)[0]
    assert row[3] == "Interviewing"
    assert row[5] == job_tracker.date.today().isoformat()


def test_update_picks_most_recent_when_multiple_match(db_path):
    """When company/role matches more than one row, only the most recently applied is updated."""
    _add(db_path, "Acme Corp", "Backend Engineer", "2026-05-01")
    _add(db_path, "Acme Corp", "Backend Engineer", "2026-07-01")

    job_tracker.main(
        ["update", "--company", "Acme Corp", "--role", "Backend Engineer", "--status", "Offer"],
        db_path=db_path,
    )

    statuses_by_date = {r[2]: r[3] for r in _rows(db_path)}
    assert statuses_by_date["2026-05-01"] == "Applied"
    assert statuses_by_date["2026-07-01"] == "Offer"


def test_update_reports_error_when_no_match(db_path, capsys):
    """Updating a company/role with no matching application errors and changes nothing."""
    exit_code = job_tracker.main(
        ["update", "--company", "Nowhere LLC", "--role", "Ghost Role", "--status", "Offer"],
        db_path=db_path,
    )

    assert exit_code == 1
    assert "no matching application" in capsys.readouterr().err
    assert _rows(db_path) == []


def test_update_match_is_case_and_whitespace_insensitive(db_path):
    """Matching ignores letter case and leading/trailing whitespace in company and role."""
    _add(db_path, "Acme Corp", "Backend Engineer", "2026-07-01")

    exit_code = job_tracker.main(
        ["update", "--company", " acme corp ", "--role", " backend engineer ", "--status", "Interviewing"],
        db_path=db_path,
    )

    assert exit_code == 0
    assert _rows(db_path)[0][3] == "Interviewing"


def test_stale_lists_only_overdue_active_applications(db_path, capsys):
    """Stale shows active applications untouched 14+ days, and excludes terminal statuses."""
    today = job_tracker.date.today()
    _add_with_last_updated(db_path, "Acme Corp", "Backend Engineer", "Applied", (today - timedelta(days=20)).isoformat())
    _add_with_last_updated(db_path, "Beta Inc", "Data Analyst", "Interviewing", (today - timedelta(days=5)).isoformat())
    _add_with_last_updated(db_path, "Gamma LLC", "Designer", "Rejected", (today - timedelta(days=30)).isoformat())

    exit_code = job_tracker.main(["stale"], db_path=db_path)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Acme Corp" in output
    assert "Beta Inc" not in output
    assert "Gamma LLC" not in output


def test_data_persists_across_separate_runs(db_path):
    """Data added in one invocation of the tool is still present in a later, separate invocation."""
    job_tracker.main(
        ["add", "--company", "Acme Corp", "--role", "Backend Engineer",
         "--date-applied", "2026-07-01", "--status", "Applied"],
        db_path=db_path,
    )
    job_tracker.main(
        ["update", "--company", "Acme Corp", "--role", "Backend Engineer", "--status", "Offer"],
        db_path=db_path,
    )

    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0][3] == "Offer"


def test_full_workflow_add_list_update_stale(db_path, capsys):
    """A full add -> list -> update -> stale cycle behaves consistently end to end."""
    job_tracker.main(
        ["add", "--company", "Acme Corp", "--role", "Backend Engineer",
         "--date-applied", (job_tracker.date.today() - timedelta(days=20)).isoformat(), "--status", "Applied"],
        db_path=db_path,
    )
    job_tracker.main(["list"], db_path=db_path)
    assert "Acme Corp" in capsys.readouterr().out

    job_tracker.main(["stale"], db_path=db_path)
    assert "Acme Corp" in capsys.readouterr().out

    job_tracker.main(
        ["update", "--company", "Acme Corp", "--role", "Backend Engineer", "--status", "Rejected"],
        db_path=db_path,
    )
    job_tracker.main(["stale"], db_path=db_path)
    assert "Acme Corp" not in capsys.readouterr().out
