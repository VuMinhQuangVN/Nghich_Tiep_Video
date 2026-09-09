"""Video model selection for the Agnes adapter."""
from __future__ import annotations
from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class VideoEngineSelection:
    client: object
    model_name: str
    fallback_model: str | None = None


def build_video_engine(client, video_engine: str = "auto") -> VideoEngineSelection:
    """Resolve the UI engine name to a concrete supported model."""
    name = (video_engine or "auto").strip().lower()
    if name in {"agnes-v2", "v2", "v2.0", "stable"}:
        return VideoEngineSelection(client, settings.agnes_models.video_stable, None)
    # The current production path is Agnes Video 2.5 Flash with V2.0 as the
    # stable fallback.  Older experimental/trial switches are intentionally
    # no longer part of the Creative UI.
    return VideoEngineSelection(
        client,
        settings.agnes_models.video,
        settings.agnes_models.video_stable,
    )
