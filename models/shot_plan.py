"""Phase 6: Shot-level planning contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CreativeShot:
    """A concrete camera shot inside a CreativeScene.

    ``generation_prompt`` is intentionally a shot-level draft. Phase 7 will
    compose the final engine prompt with product/character/style consistency.
    """

    index: int
    shot_type: str = ""
    framing: str = ""
    camera_angle: str = ""
    camera_motion: str = ""
    subject_position: str = ""
    action: str = ""
    environment: str = ""
    lighting: str = ""
    duration_sec: float = 1.0
    generation_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
