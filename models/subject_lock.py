from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SubjectLock:
    """
    Canonical visual-consistency contract for a generated video.

    The product is always the primary locked subject. Character locking is
    optional and is enabled only when CreativeDirector requires a character.
    """

    subject_type: str = "product"
    reference_urls: list[str] = field(default_factory=list)

    # Product identity that must survive across every shot.
    identity_features: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)

    # Character lock is optional.
    character_required: bool = False
    character_description: str = ""
    character_reference_url: str | None = None

    def validate(self) -> None:
        if self.subject_type != "product":
            raise ValueError("SubjectLock.subject_type must be 'product'")

        if not self.reference_urls:
            raise ValueError("SubjectLock requires at least one reference URL")

        if not self.identity_features:
            raise ValueError("SubjectLock requires product identity features")

        if self.character_required and not self.character_description.strip():
            raise ValueError(
                "Character description is required when character_required=True"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_type": self.subject_type,
            "reference_urls": list(self.reference_urls),
            "identity_features": list(self.identity_features),
            "invariants": list(self.invariants),
            "character_required": self.character_required,
            "character_description": self.character_description,
            "character_reference_url": self.character_reference_url,
        }
