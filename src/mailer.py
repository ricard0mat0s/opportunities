"""Secure SMTP_SSL email dispatcher with Markdown-to-HTML rendering.

Converts the synthesized Markdown report into a responsive HTML email and
dispatches it via Gmail SMTP_SSL without logging email addresses, credentials,
or report contents.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import markdown

from src.config import AppConfig, get_logger

logger = get_logger()

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Remote Tech Internship Radar</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #1f2937;
    background-color: #f9fafb;
    margin: 0;
    padding: 24px;
  }}
  .container {{
    max-width: 760px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 28px 32px;
  }}
  h1, h2, h3 {{
    color: #111827;
  }}
  h1 {{
    border-bottom: 2px solid #2563eb;
    padding-bottom: 10px;
  }}
  h2 {{
    margin-top: 24px;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 6px;
  }}
  a {{
    color: #2563eb;
    text-decoration: none;
  }}
  a:hover {{
    text-decoration: underline;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
  }}
  th, td {{
    border: 1px solid #d1d5db;
    padding: 8px 12px;
    text-align: left;
  }}
  th {{
    background-color: #f3f4f6;
  }}
  code {{
    background-color: #f3f4f6;
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 0.9em;
  }}
  .footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
    font-size: 0.85em;
    color: #6b7280;
  }}
</style>
</head>
<body>
  <div class="container">
    {body_html}
    <div class="footer">
      Generated automatically by Weekly Remote Internship Radar.
    </div>
  </div>
</body>
</html>
"""


class MailerError(Exception):
    """Raised when email conversion or SMTP_SSL delivery fails."""


def markdown_to_html(markdown_text: str) -> str:
    """Convert Markdown report text into a styled HTML email document."""
    if not markdown_text or not markdown_text.strip():
        raise MailerError("Cannot render empty Markdown report.")

    rendered_body = markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    return _HTML_TEMPLATE.format(body_html=rendered_body)


def send_report_email(
    config: AppConfig,
    markdown_report: str,
    subject: Optional[str] = None,
) -> None:
    """Render Markdown to HTML and dispatch via SMTP_SSL."""
    html_content = markdown_to_html(markdown_report)
    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    email_subject = subject or f"Weekly Remote Tech Internship Radar ({date_label})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject
    msg["From"] = config.smtp_user
    msg["To"] = config.recipient_email

    msg.attach(MIMEText(markdown_report, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(
            host=config.smtp_host,
            port=config.smtp_port,
            context=context,
            timeout=30,
        ) as server:
            server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)
        logger.info("Email dispatched successfully.")
    except Exception as exc:
        logger.error(f"Failed to dispatch email ({type(exc).__name__}).")
        raise MailerError("SMTP email dispatch failed.") from None
