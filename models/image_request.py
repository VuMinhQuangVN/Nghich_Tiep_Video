"""Stable image-generation contracts and Agnes Image 2.1 normalization."""
from __future__ import annotations

from dataclasses import dataclass, field

SUPPORTED_IMAGE_RATIOS = ("1:1", "3:4", "4:3", "16:9", "9:16", "2:3", "3:2", "21:9")
SUPPORTED_IMAGE_RESOLUTIONS = ("1K", "2K", "3K", "4K")
PLATFORM_IMAGE_RATIOS = {
    "tiktok": "9:16",
    "instagram": "9:16",
    "instagram reels": "9:16",
    "youtube shorts": "9:16",
    "facebook": "9:16",
    "youtube": "16:9",
}


def normalize_image_ratio(value: str | None) -> str:
    ratio = (value or "1:1").strip()
    if ratio not in SUPPORTED_IMAGE_RATIOS:
        raise ValueError(f"Unsupported Agnes Image ratio: {ratio!r}")
    return ratio


def normalize_image_resolution(value: str | None) -> str:
    resolution = (value or "2K").strip().upper()
    if resolution not in SUPPORTED_IMAGE_RESOLUTIONS:
        raise ValueError(f"Unsupported Agnes Image resolution: {resolution!r}")
    return resolution


def image_ratio_for_platform(platform: str | None) -> str:
    key = (platform or "").strip().lower()
    return PLATFORM_IMAGE_RATIOS.get(key, "9:16")


@dataclass(frozen=True)
class ImageReference:
    value: str

    def validate(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("ImageReference.value must not be empty")
        if value.startswith("data:image/") and ";base64," in value[:128]:
            return
        if value.startswith(("http://", "https://")):
            return
        raise ValueError("ImageReference must be a public URL or image Data URI")


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    ratio: str = "9:16"
    resolution: str = "2K"
    references: list[ImageReference] = field(default_factory=list)

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("ImageGenerationRequest.prompt must not be empty")
        normalize_image_ratio(self.ratio)
        normalize_image_resolution(self.resolution)
        for reference in self.references:
            reference.validate()

    def reference_values(self) -> list[str]:
        self.validate()
        return [reference.value.strip() for reference in self.references]
