"""
models/creative_plan.py
-----------------------
Phase 1: Data contract for the AI creative pipeline.

CreativePlan is the intermediate representation between the future
AI Creative Director and the existing video-generation pipeline.

No AI/network calls and no Agnes-specific logic live here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass
class CreativeInput:
    product_reference_urls: list[str] = field(default_factory=list)
    goal: str = ""
    platform: str = ""
    duration_sec: float = 30.0
    language: str = "vi"


@dataclass
class ProductProfile:
    name: str = ""
    category: str = ""
    description: str = ""
    visual_identity: list[str] = field(default_factory=list)
    selling_points: list[str] = field(default_factory=list)
    consistency_requirements: list[str] = field(default_factory=list)


@dataclass
class AudienceProfile:
    age_range: str = ""
    gender: str = ""
    interests: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)


@dataclass
class CreativeConcept:
    title: str = ""
    description: str = ""
    hook: str = ""


@dataclass
class VisualStyle:
    style: str = ""
    lighting: str = ""
    color_palette: list[str] = field(default_factory=list)
    camera_style: str = ""
    mood: str = ""


@dataclass
class CharacterProfile:
    required: bool = False
    description: str = ""
    reference_url: str | None = None


@dataclass
class ScriptPlan:
    voiceover: str = ""
    text_overlays: list[str] = field(default_factory=list)
    cta: str = ""


@dataclass
class CreativeScene:
    index: int
    objective: str = ""
    description: str = ""
    duration_sec: float = 4.0
    camera: str = ""
    camera_motion: str = ""
    framing: str = ""
    product_visibility: str = ""
    product_position: str = ""
    character_action: str = ""
    environment: str = ""
    lighting: str = ""
    mood: str = ""
    transition: str = ""
    voiceover: str = ""
    text_overlay: str = ""
    cta: str = ""


@dataclass
class CreativePlan:
    input: CreativeInput = field(default_factory=CreativeInput)
    product: ProductProfile = field(default_factory=ProductProfile)
    audience: AudienceProfile = field(default_factory=AudienceProfile)
    concept: CreativeConcept = field(default_factory=CreativeConcept)
    visual_style: VisualStyle = field(default_factory=VisualStyle)
    character: CharacterProfile = field(default_factory=CharacterProfile)
    script: ScriptPlan = field(default_factory=ScriptPlan)
    scenes: list[CreativeScene] = field(default_factory=list)

    def validate(self) -> None:
        if not self.input.product_reference_urls:
            raise ValueError("CreativePlan requires at least one product reference URL")

        for url in self.input.product_reference_urls:
            if not _looks_like_url(url):
                raise ValueError(f"Invalid product reference URL: {url!r}")

        if not self.input.goal.strip():
            raise ValueError("CreativePlan.input.goal must not be empty")

        if not self.input.platform.strip():
            raise ValueError("CreativePlan.input.platform must not be empty")

        if self.input.duration_sec <= 0:
            raise ValueError("CreativePlan.input.duration_sec must be greater than 0")

        if self.character.required and not self.character.description.strip():
            raise ValueError(
                "CharacterProfile.description is required when character.required=True"
            )

        if not self.scenes:
            raise ValueError("CreativePlan requires at least one scene")

        expected_index = 1
        total_duration = 0.0

        for scene in self.scenes:
            if scene.index != expected_index:
                raise ValueError(
                    "CreativeScene indexes must be sequential starting from 1 "
                    f"(expected {expected_index}, got {scene.index})"
                )

            if scene.duration_sec <= 0:
                raise ValueError(
                    f"Scene {scene.index} duration_sec must be greater than 0"
                )

            total_duration += scene.duration_sec
            expected_index += 1

        # AI may round scene durations, so allow a 25% upper tolerance.
        if total_duration > self.input.duration_sec * 1.25:
            raise ValueError(
                "Total scene duration is more than 25% above requested video duration"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _looks_like_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
