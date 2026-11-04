"""Secure configuration loader and logger setup.

Enforces zero-leakage guardrails:
- Sensitive fields are excluded from string representations.
- Validation errors report only the variable name, never its value.
- Logger filter prevents stack traces and exception payloads from leaking into public CI logs.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConfigurationError(Exception):
    """Raised when required environment configuration is missing or invalid."""


class _RedactingLogFilter(logging.Filter):
    """Strips exc_info and stack_info so stack traces never dump local vars in CI logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def get_logger(name: str = "internship_radar") -> logging.Logger:
    """Return a security-hardened logger that outputs only generic milestone messages."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handler.addFilter(_RedactingLogFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration with redacted representations."""

    gemini_api_key: str = field(repr=False)
    smtp_user: str = field(repr=False)
    smtp_password: str = field(repr=False)
    recipient_email: str = field(repr=False)
    gemini_model: str = "gemini-2.5-flash"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    jina_api_key: Optional[str] = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            f"AppConfig(gemini_model={self.gemini_model!r}, "
            f"smtp_host={self.smtp_host!r}, smtp_port={self.smtp_port!r}, "
            "secrets='[REDACTED]')"
        )

    def __str__(self) -> str:
        return self.__repr__()


def _require_env(var_name: str) -> str:
    """Retrieve a non-empty environment variable or raise ConfigurationError."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        raise ConfigurationError(f"Missing required environment variable: {var_name}")
    return val


def _validate_email(var_name: str, value: str) -> str:
    """Validate basic email syntax without leaking the value on failure."""
    if not _EMAIL_PATTERN.match(value):
        raise ConfigurationError(f"Invalid email format in environment variable: {var_name}")
    return value


def load_config(load_env_file: bool = True) -> AppConfig:
    """Load and validate configuration from environment variables safely."""
    if load_env_file:
        load_dotenv(override=False)

    gemini_api_key = _require_env("GEMINI_API_KEY")
    smtp_user = _validate_email("SMTP_USER", _require_env("SMTP_USER"))
    smtp_password = _require_env("SMTP_PASSWORD")
    recipient_email = _validate_email("RECIPIENT_EMAIL", _require_env("RECIPIENT_EMAIL"))

    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"

    raw_port = os.environ.get("SMTP_PORT", "465").strip()
    try:
        smtp_port = int(raw_port)
        if not (1 <= smtp_port <= 65535):
            raise ValueError
    except ValueError as exc:
        raise ConfigurationError("Invalid integer port in environment variable: SMTP_PORT") from exc

    jina_api_key = os.environ.get("JINA_API_KEY", "").strip() or None

    return AppConfig(
        gemini_api_key=gemini_api_key,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        recipient_email=recipient_email,
        gemini_model=gemini_model,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        jina_api_key=jina_api_key,
    )
