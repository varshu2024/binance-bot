"""
Structured logging configuration for the trading bot.
Writes logs to both the console and a rotating log file.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")

_CONFIGURED = False


def setup_logging(level: int = logging.DEBUG) -> None:
    """Initialise root logger with console + file handlers (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- rotating file handler (keeps last 5 × 5 MB) ---
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # --- console handler (INFO and above) ---
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(ch)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (logging must already be configured)."""
    return logging.getLogger(name)
