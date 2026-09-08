import logging
import sys
import re

SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|password|token)[\"']?\s*[:=]\s*[\"']?([^\"'\s,]+)", re.IGNORECASE),
    re.compile(r"bearer\s+([a-zA-Z0-9\-\._~\+\/]+=*)", re.IGNORECASE),
]


class SensitiveDataFilter(logging.Filter):
    """Filters out passwords, secret keys, and API tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in SENSITIVE_PATTERNS:
                msg = pattern.sub(r"\1=***REDACTED***", msg)
            record.msg = msg
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide structured logging."""
    logger = logging.getLogger("reposage")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    # Avoid duplicate handlers
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False
