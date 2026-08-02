#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

VALID_STATUSES = ("Applied", "Interviewing", "Offer", "Rejected", "Withdrawn")
ACTIVE_STATUSES = ("Applied", "Interviewing")
STALE_DAYS = 14

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    date_applied TEXT NOT NULL,
    status TEXT NOT NULL,
    referral_contact TEXT NOT NULL DEFAULT '',
    last_updated TEXT NOT NULL
);
"""

LIST_HEADERS = ["ID", "Company", "Role", "Date Applied", "Status", "Referral", "Last Updated"]


def default_db_path() -> Path:
    return Path.home() / ".job-tracker" / "applications.db"


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def normalize_status(raw: str) -> str:
    for canonical in VALID_STATUSES:
        if raw.strip().lower() == canonical.lower():
            return canonical
    raise ValueError(f"invalid status '{raw}', must be one of {', '.join(VALID_STATUSES)}")


def parse_iso_date(raw: str) -> str:
    date.fromisoformat(raw)
    return raw


def format_table(rows, headers) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))

    def fmt_row(vals):
        return "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(vals))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def cmd_add(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    try:
        status = normalize_status(args.status)
        date_applied = parse_iso_date(args.date_applied)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    referral = args.referral or ""
    cur = conn.execute(
        "INSERT INTO applications (company, role, date_applied, status, referral_contact, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (args.company, args.role, date_applied, status, referral, date_applied),
    )
    conn.commit()
    print(f"added application {cur.lastrowid}")
    return 0


def cmd_list(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    rows = conn.execute(
        "SELECT id, company, role, date_applied, status, referral_contact, last_updated "
        "FROM applications ORDER BY date_applied DESC"
    ).fetchall()
    print(format_table(rows, LIST_HEADERS))
    return 0


def cmd_update(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    try:
        status = normalize_status(args.status)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    candidates = conn.execute(
        "SELECT id, date_applied FROM applications "
        "WHERE lower(trim(company)) = lower(trim(?)) AND lower(trim(role)) = lower(trim(?))",
        (args.company, args.role),
    ).fetchall()
    if not candidates:
        print(f"error: no matching application found for '{args.company}' / '{args.role}'", file=sys.stderr)
        return 1
    target_id = max(candidates, key=lambda r: (r[1], r[0]))[0]
    today = date.today().isoformat()
    conn.execute(
        "UPDATE applications SET status = ?, last_updated = ? WHERE id = ?",
        (status, today, target_id),
    )
    conn.commit()
    print(f"updated application {target_id} to status '{status}'")
    return 0


def cmd_stale(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    rows = conn.execute(
        f"SELECT id, company, role, date_applied, status, referral_contact, last_updated "
        f"FROM applications WHERE status IN ({placeholders}) "
        f"AND julianday('now') - julianday(last_updated) >= ?",
        (*ACTIVE_STATUSES, STALE_DAYS),
    ).fetchall()
    print(format_table(rows, LIST_HEADERS))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job_tracker.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_p = subparsers.add_parser("add")
    add_p.add_argument("--company", required=True)
    add_p.add_argument("--role", required=True)
    add_p.add_argument("--date-applied", required=True, dest="date_applied")
    add_p.add_argument("--status", required=True)
    add_p.add_argument("--referral", default="")
    add_p.set_defaults(func=cmd_add)

    list_p = subparsers.add_parser("list")
    list_p.set_defaults(func=cmd_list)

    update_p = subparsers.add_parser("update")
    update_p.add_argument("--company", required=True)
    update_p.add_argument("--role", required=True)
    update_p.add_argument("--status", required=True)
    update_p.set_defaults(func=cmd_update)

    stale_p = subparsers.add_parser("stale")
    stale_p.set_defaults(func=cmd_stale)

    return parser


def main(argv=None, db_path: Path = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    conn = get_connection(db_path or default_db_path())
    try:
        return args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
