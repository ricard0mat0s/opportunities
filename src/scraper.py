"""Job board scraper using Jina Reader API with prompt-injection isolation.

Fetches clean Markdown snapshots from remote job boards and encapsulates all
external text inside `<untrusted_scraped_content>` XML tags after neutralizing
any nested tag-breakout attempts.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence, Tuple

import requests

from src.config import get_logger

logger = get_logger()

JINA_READER_BASE_URL = "https://r.jina.ai/"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_CHARS_PER_BOARD = 12_000

DEFAULT_TARGET_BOARDS: Tuple[Tuple[str, str], ...] = (
    ("Remotive Software Dev", "https://remotive.com/remote-jobs/software-dev"),
    ("WeWorkRemotely Programming", "https://weworkremotely.com/categories/remote-programming-jobs"),
    ("Himalayas Remote Internships", "https://himalayas.app/jobs/internships"),
    (
        "Simplify Tech Internships",
        "https://github.com/SimplifyJobs/Summer2025-Internships/blob/dev/README.md",
    ),
)

_TAG_BREAKOUT_PATTERN = re.compile(
    r"</?\s*untrusted_scraped_content[^>]*>",
    re.IGNORECASE,
)


def sanitize_untrusted_text(raw_text: str, max_chars: int = MAX_CHARS_PER_BOARD) -> str:
    """Neutralize XML sandbox breakout tags and cap content length."""
    if not raw_text:
        return ""
    cleaned = _TAG_BREAKOUT_PATTERN.sub("[REDACTED_TAG]", raw_text)
    return cleaned.strip()[:max_chars]


def wrap_untrusted_content(source_name: str, raw_text: str) -> str:
    """Wrap external scraped text inside `<untrusted_scraped_content>` tags."""
    safe_source = re.sub(r"[^a-zA-Z0-9_\-\s().]", "", source_name).strip() or "unknown_board"
    sanitized_body = sanitize_untrusted_text(raw_text)
    return (
        f'<untrusted_scraped_content source="{safe_source}">\n'
        f"{sanitized_body}\n"
        f"</untrusted_scraped_content>"
    )


def fetch_board_markdown(
    board_name: str,
    target_url: str,
    jina_api_key: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Fetch clean Markdown from a single job board via Jina Reader."""
    jina_url = f"{JINA_READER_BASE_URL}{target_url}"
    headers = {
        "Accept": "text/plain",
        "X-Return-Format": "markdown",
        "User-Agent": "WeeklyInternshipRadar/1.0",
    }
    if jina_api_key:
        headers["Authorization"] = f"Bearer {jina_api_key}"

    try:
        response = requests.get(jina_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            logger.warning("Empty snapshot returned from board source.")
            return None
        return wrap_untrusted_content(board_name, text)
    except Exception as exc:
        logger.warning(f"Failed to fetch board snapshot ({type(exc).__name__}). Continuing...")
        return None


def fetch_all_boards(
    boards: Sequence[Tuple[str, str]] = DEFAULT_TARGET_BOARDS,
    jina_api_key: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch and wrap Markdown snapshots from all configured target job boards."""
    snapshots: list[str] = []
    for board_name, target_url in boards:
        wrapped = fetch_board_markdown(
            board_name=board_name,
            target_url=target_url,
            jina_api_key=jina_api_key,
            timeout=timeout,
        )
        if wrapped:
            snapshots.append(wrapped)

    logger.info("Board snapshots fetched.")
    if not snapshots:
        return (
            '<untrusted_scraped_content source="none">\n'
            "No external board snapshots were available during this run.\n"
            "</untrusted_scraped_content>"
        )
    return "\n\n".join(snapshots)
