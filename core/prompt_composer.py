"""Prompt composition for the AI creative pipeline.

Phase 7 introduces :class:`PromptComposer`, which turns the approved
CreativePlan + SubjectLock + Scene + Shot into a final, consistency-heavy
engine prompt.  It deliberately does not call an LLM or any network service.
"""
from __future__ import annotations

from typing import Any

from models.creative_plan import CreativePlan, CreativeScene
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock


class PromptComposer:
    """Compose deterministic final prompts from already-approved data."""

    def compose_shot_prompt(
        self,
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
        scene: CreativeScene,
        shot: CreativeShot,
    ) -> str:
        self._validate(creative_plan, subject_lock, scene, shot)

        product = creative_plan.product
        style = creative_plan.visual_style
        character = creative_plan.character

        sections = [
            "GLOBAL CONSISTENCY",
            self._lines(
                "Maintain one continuous visual identity across the entire video.",
                f"Overall visual style: {style.style}",
                f"Overall mood: {style.mood}",
                f"Global camera style: {style.camera_style}",
                f"Global lighting style: {style.lighting}",
                f"Color palette: {self._join(style.color_palette)}",
            ),
            "PRODUCT CONSISTENCY",
            self._lines(
                f"Product name: {product.name}",
                f"Product category: {product.category}",
                f"Product description: {product.description}",
                f"Product visual identity: {self._join(product.visual_identity)}",
                f"Product selling points: {self._join(product.selling_points)}",
                "Product reference must remain the same physical object in every shot.",
            ),
        ]

        if subject_lock.character_required:
            sections.extend(
                [
                    "CHARACTER CONSISTENCY",
                    self._lines(
                        f"Character: {character.description or subject_lock.character_description}",
                        f"Character lock: {subject_lock.character_description}",
                        "Keep the same face, body identity, hairstyle, wardrobe and visual appearance across shots.",
                    ),
                ]
            )
        else:
            sections.extend(["CHARACTER CONSISTENCY", "No character is present. Do not introduce a person or model."])

        sections.extend(
            [
                "SHOT DESCRIPTION",
                self._lines(
                    f"Scene objective: {scene.objective}",
                    f"Scene description: {scene.description}",
                    f"Product visibility: {scene.product_visibility}",
                    f"Product position: {scene.product_position}",
                    f"Shot type: {shot.shot_type}",
                    f"Shot action: {shot.action}",
                    f"Environment: {shot.environment or scene.environment}",
                    f"Subject position: {shot.subject_position}",
                ),
                "CAMERA",
                self._lines(
                    f"Framing: {shot.framing or scene.framing}",
                    f"Camera angle: {shot.camera_angle}",
                    f"Camera motion: {shot.camera_motion or scene.camera_motion}",
                    f"Scene camera direction: {scene.camera}",
                ),
                "LIGHTING",
                self._lines(
                    f"Lighting: {shot.lighting or scene.lighting or style.lighting}",
                    f"Mood: {scene.mood or style.mood}",
                ),
                "MOTION",
                self._lines(
                    f"Action/motion: {shot.action}",
                    f"Duration: {shot.duration_sec:g}s",
                    f"Transition context: {scene.transition}",
                ),
                "NEGATIVE CONSTRAINTS",
                self._negative_constraints(subject_lock),
            ]
        )

        return "\n\n".join(section for section in sections if section.strip())

    # Alias with a concise API for callers that prefer "compose".
    def compose(
        self,
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
        scene: CreativeScene,
        shot: CreativeShot,
    ) -> str:
        return self.compose_shot_prompt(creative_plan, subject_lock, scene, shot)

    @staticmethod
    def _validate(
        plan: CreativePlan,
        lock: SubjectLock,
        scene: CreativeScene,
        shot: CreativeShot,
    ) -> None:
        if not isinstance(plan, CreativePlan):
            raise TypeError("PromptComposer requires a CreativePlan")
        if not isinstance(lock, SubjectLock):
            raise TypeError("PromptComposer requires a SubjectLock")
        if not isinstance(scene, CreativeScene):
            raise TypeError("PromptComposer requires a CreativeScene")
        if not isinstance(shot, CreativeShot):
            raise TypeError("PromptComposer requires a CreativeShot")

        lock.validate()
        if plan.character.required != lock.character_required:
            raise ValueError("CreativePlan and SubjectLock character state must match")
        if scene.index <= 0 or shot.index <= 0:
            raise ValueError("Scene and shot indexes must be positive")
        if shot.duration_sec <= 0:
            raise ValueError("Shot duration_sec must be greater than 0")

        if not lock.character_required and PromptComposer._mentions_character(
            f"{shot.action} {scene.character_action}"
        ):
            raise ValueError("Prompt cannot introduce character when character lock is disabled")

    @staticmethod
    def _negative_constraints(lock: SubjectLock) -> str:
        constraints = list(lock.invariants)
        constraints.extend(
            [
                "Do not redesign, replace or mutate the product.",
                "Do not change logo, packaging, shape, color, proportions or key visual identity.",
                "Do not invent unsupported product features or marketing claims.",
                "Do not introduce extra products that could be confused with the locked product.",
            ]
        )
        if not lock.character_required:
            constraints.append("Do not introduce a character, person or model.")
        else:
            constraints.append("Do not change the locked character identity or appearance.")
        return "\n".join(f"- {item}" for item in PromptComposer._unique(constraints))

    @staticmethod
    def _lines(*values: str) -> str:
        return "\n".join(value for value in values if value and value.strip())

    @staticmethod
    def _join(values: list[str]) -> str:
        return ", ".join(value.strip() for value in values if isinstance(value, str) and value.strip()) or "not specified"

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                result.append(value)
        return result

    @staticmethod
    def _mentions_character(text: str) -> bool:
        markers = (
            "character", "person", "woman", "man", "model", "girl", "boy",
            "nhân vật", "người mẫu", "cô gái", "chàng trai", "người phụ nữ", "người đàn ông",
        )
        lowered = text.lower()
        return any(marker in lowered for marker in markers)


# ---------------------------------------------------------------------------
# Backward-compatible Phase 0-4/legacy helpers.
# ---------------------------------------------------------------------------


def character_sheet_prompt(subject_description: str, style: str, num_angles: int = 4) -> str:
    return (
        f"Character reference sheet, {num_angles} turnaround angles: front view, "
        f"3/4 left, 3/4 right, back view, close-up on face/key detail.\n"
        f"Subject: {subject_description}.\n"
        f"Style: {style}.\n"
        f"Consistent lighting, neutral background, same subject across all angles, "
        f"high detail, production-ready reference sheet."
    )


def scene_image_prompt(scene_description: str, style: str, mood: str = "") -> str:
    return (
        f"{scene_description}, subject consistent with reference image, "
        f"style: {style}, {mood}."
    )


def keyframe_image_prompt(moment_description: str, style: str) -> str:
    return (
        f"{moment_description}, subject consistent with reference image, "
        f"style: {style}."
    )


def keyframe_video_prompt(subject_name: str, mood: str = "") -> str:
    return (
        f"Generate a smooth cinematic transition through these keyframes in order, "
        f"maintaining {subject_name} identity, consistent camera angle logic, "
        f"and natural motion between each keyframe. {mood}."
    )


def scene_video_prompt(action_desc: str, camera_move: str, mood: str, duration_sec: float) -> str:
    return (
        f"{action_desc}, camera: {camera_move}, mood: {mood}, "
        f"duration {duration_sec:.0f}s. "
        f"Maintain exact subject appearance and style from the reference image."
    )


def single_shot_video_prompt(action_desc: str, camera_move: str, mood: str, duration_sec: float) -> str:
    return f"{action_desc}, camera: {camera_move}, mood: {mood}, duration {duration_sec:.0f}s."
