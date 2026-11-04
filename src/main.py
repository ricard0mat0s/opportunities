"""Main entrypoint orchestrating the Weekly Remote Internship Radar pipeline."""

from __future__ import annotations

import sys

from src.config import get_logger, load_config
from src.mailer import send_report_email
from src.scraper import fetch_all_boards
from src.search_agent import generate_internship_report

logger = get_logger()


def run_pipeline() -> int:
    """Execute the end-to-end internship discovery and email delivery pipeline."""
    logger.info("Starting weekly internship search...")
    try:
        config = load_config()
        snapshots = fetch_all_boards(jina_api_key=config.jina_api_key)
        report_markdown = generate_internship_report(config=config, scraped_snapshots=snapshots)
        send_report_email(config=config, markdown_report=report_markdown)
        return 0
    except Exception as exc:
        logger.error(f"Pipeline execution failed ({type(exc).__name__}).")
        return 1


def main() -> None:
    """CLI entrypoint."""
    sys.exit(run_pipeline())


if __name__ == "__main__":
    main()
