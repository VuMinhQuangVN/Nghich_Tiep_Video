"""
models/image_request.py
------------------------
Data model cho image generation request.
"""
from __future__ import annotations
from dataclasses import dataclass, field


def normalize_image_ratio(ratio: str) -> str:
    mapping = {
        "16:9": "16:9", "9:16": "9:16", "1:1": "1:1",
        "4:3": "4:3", "3:4": "3:4",
    }
    return mapping.get(ratio.strip(), "9:16")


def normalize_image_resolution(resolution: str) -> str:
    mapping = {
        "2K": "2048x2048", "1K": "1024x1024",
        "512": "512x512", "HD": "1280x720",
    }
    return mapping.get(resolution.strip(), resolution)


@dataclass
class ImageReference:
    value: str  # URL hoặc base64 data URI


@dataclass
class ImageGenerationRequest:
    prompt: str
    ratio: str = "9:16"
    resolution: str = "2K"
    references: list[ImageReference] = field(default_factory=list)

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Prompt không được để trống")

    def reference_values(self) -> list[str]:
        return [r.value for r in self.references if r.value]
