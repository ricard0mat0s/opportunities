# Automated Weekly Remote Internship Radar

A production-ready, security-hardened Python pipeline and GitHub Actions workflow that runs every **Monday at 08:00 AM BRT (11:00 UTC)** to discover open remote technology internships via Jina Reader snapshots + Google Gemini Search Grounding (`google-genai`), and delivers a curated HTML email report via `SMTP_SSL`.

---

## Security Architecture & Guardrails

Because this repository is designed to run safely as a **public GitHub repository**, the following DevSecOps controls are strictly enforced:

1. **Zero Secret or PII Leakage in Public CI Logs:**
   - Environment variables, API keys, SMTP credentials, email addresses, and synthesized report contents are **never** printed or logged to `stdout` or `stderr`.
   - `AppConfig` redacts all sensitive fields in `__repr__` and `__str__`.
   - A custom `_RedactingLogFilter` strips `exc_info` and stack traces from log records, and exception handlers log only `type(e).__name__` with generic operational milestones.
2. **Prompt Injection Isolation:**
   - External job board text fetched via Jina Reader is treated as untrusted input.
   - Any nested `<untrusted_scraped_content>` or `</untrusted_scraped_content>` breakout tags in scraped pages are neutralized before wrapping each snapshot in `<untrusted_scraped_content source="...">...</untrusted_scraped_content>`.
   - Duties are strictly separated: Python handles all HTTP fetching and `SMTP_SSL` delivery; the Gemini model (`google-genai`) is restricted strictly to text synthesis and `GoogleSearch` grounding with no code execution, shell tools, or environment variable access.
3. **GitHub Actions Principle of Least Privilege:**
   - Triggered strictly on `schedule` (`cron: '0 11 * * 1'`) and `workflow_dispatch` (never `pull_request` or `pull_request_target`).
   - Top-level workflow permissions are locked down to `permissions: contents: read` with `persist-credentials: false` on checkout.
4. **Repository Hygiene:**
   - Strict `.gitignore` prevents accidental commits of `.env` files, keys, logs, virtual environments, caches, and local HTML/Markdown report outputs.

---

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── weekly_internships.yml
├── src/
│   ├── __init__.py
│   ├── config.py          # Loads & validates env vars safely with redacted repr
│   ├── scraper.py         # Fetches clean Markdown from target job boards via Jina Reader
│   ├── search_agent.py    # Calls Gemini API (google-genai) with Google Search grounding
│   ├── mailer.py          # Converts Markdown to HTML & sends via SMTP_SSL (Gmail App Password)
│   └── main.py            # Entrypoint orchestrating the pipeline
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py   # pytest unit tests mocking HTTP, Gemini API, and SMTP
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Configuration & Setup

### 1. Required Secrets / Environment Variables

Copy `.env.example` to `.env` for local runs, or configure the following **GitHub Actions Repository Secrets** (`Settings -> Secrets and variables -> Actions`):

| Variable | Required | Description |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (`google-genai` SDK) |
| `SMTP_USER` | Yes | Sender Gmail address |
| `SMTP_PASSWORD` | Yes | 16-character Gmail App Password |
| `RECIPIENT_EMAIL` | Yes | Destination email address for the curated report |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.5-flash` |
| `SMTP_HOST` | No | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | No | Defaults to `465` (`SMTP_SSL`) |
| `JINA_API_KEY` | No | Optional Jina Reader API key for higher rate limits |

### 2. Local Installation & Testing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run unit tests
pytest -v

# Run pipeline locally (requires .env configured)
python -m src.main
```
