"""Normalized Agnes error classification for retry/routing decisions."""
from __future__ import annotations
from enum import Enum

class AgnesErrorKind(str, Enum):
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    NETWORK = "network"
    TIMEOUT = "timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    UNKNOWN = "unknown"


def classify_status(status: int) -> AgnesErrorKind:
    if status in (401, 403): return AgnesErrorKind.AUTH
    if status == 429: return AgnesErrorKind.RATE_LIMIT
    if 400 <= status < 500: return AgnesErrorKind.INVALID_REQUEST
    if 500 <= status < 600: return AgnesErrorKind.SERVER
    return AgnesErrorKind.UNKNOWN


def is_fallback_worthy(kind: AgnesErrorKind) -> bool:
    return kind in {AgnesErrorKind.RATE_LIMIT, AgnesErrorKind.SERVER, AgnesErrorKind.NETWORK, AgnesErrorKind.TIMEOUT, AgnesErrorKind.MODEL_UNAVAILABLE}
