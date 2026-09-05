from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.router import QuotaMode, Technique


class GenerationMode(str, Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class GenerationRequest:
    mode: GenerationMode

    # Simple Mode contract
    product_reference_url: str | None = None
    goal: str | None = None
    platform: str | None = None
    duration_sec: float | None = None

    # Advanced Mode contract
    script_text: str | None = None
    style: str = ""
    subject: str = ""
    keep_character: bool = False
    reference_image_url: str | None = None
    quota_mode: QuotaMode = QuotaMode.SAVE
    technique_override: Technique | None = None
    max_concurrent_image_requests: int | None = None
    max_concurrent_video_submit: int | None = None
    poll_interval_sec: float | None = None

    def validate(self) -> None:
        if self.mode == GenerationMode.SIMPLE:
            if not self.product_reference_url or not _looks_like_url(self.product_reference_url):
                raise ValueError("Simple Mode requires a valid product_reference_url")
            if not (self.goal or "").strip():
                raise ValueError("Simple Mode requires goal")
            if not (self.platform or "").strip():
                raise ValueError("Simple Mode requires platform")
            if self.duration_sec is None or self.duration_sec <= 0:
                raise ValueError("Simple Mode duration_sec must be greater than 0")
            return

        if self.mode == GenerationMode.ADVANCED:
            if not (self.script_text or "").strip():
                raise ValueError("Advanced Mode requires script_text")
            if self.keep_character and not (self.reference_image_url or "").strip():
                raise ValueError("reference_image_url is required when keep_character=True")
            if self.technique_override is not None and not isinstance(self.technique_override, Technique):
                raise TypeError("technique_override must be Technique or None")
            return

        raise ValueError(f"Unsupported generation mode: {self.mode!r}")


def _looks_like_url(value: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
