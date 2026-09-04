"""
utils/logger.py
----------------
1 nguồn logger duy nhất cho toàn app, dùng rich để in đẹp trên terminal.
"""
from __future__ import annotations

import logging

from rich.logging import RichHandler

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )
        _CONFIGURED = True
    return logging.getLogger(name)
