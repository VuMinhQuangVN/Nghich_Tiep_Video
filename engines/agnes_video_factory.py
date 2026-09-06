"""Build the Agnes video engine without leaking model branching into pipeline code."""
from __future__ import annotations

from config import settings
from engines.agnes_client import AgnesClient
from engines.agnes_video_25_flash import AgnesVideo25FlashAdapter
from engines.agnes_video_v20 import AgnesVideoV20Adapter
from engines.fallback_video_engine import FallbackVideoEngine
from engines.video_engine import VideoEngine


def build_agnes_video_engine(client: AgnesClient) -> VideoEngine:
    """Return stable V2.0 by default; experimental mode gets automatic fallback."""
    stable = AgnesVideoV20Adapter(client)
    if not settings.agnes_models.video_experimental_enabled:
        return stable
    experimental = AgnesVideo25FlashAdapter(client)
    return FallbackVideoEngine(experimental, stable)
