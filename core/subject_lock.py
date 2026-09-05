from __future__ import annotations

from models.creative_plan import CharacterProfile, ProductProfile
from models.subject_lock import SubjectLock


class SubjectLockBuilder:
    """
    Build the consistency contract from the already approved creative data.

    Phase 4 deliberately does not generate images or call the video engine.
    It creates the constraints that later prompt/shot stages must respect.
    """

    def build(
        self,
        reference_urls: list[str],
        product: ProductProfile,
        character: CharacterProfile | None = None,
    ) -> SubjectLock:
        urls = [url.strip() for url in reference_urls if url and url.strip()]
        if not urls:
            raise ValueError("SubjectLock requires at least one reference URL")

        if not product.name.strip() and not product.description.strip():
            raise ValueError("ProductProfile must contain product information")

        identity_features = self._unique(
            product.visual_identity
            + ([product.name] if product.name.strip() else [])
            + ([product.category] if product.category.strip() else [])
        )

        invariants = self._unique(
            product.consistency_requirements
            + [
                "Không thay đổi hình dáng, màu sắc, logo hoặc nhận diện của sản phẩm.",
                "Giữ sản phẩm là cùng một physical object giữa các shot.",
            ]
        )

        char_required = bool(character and character.required)
        char_description = character.description.strip() if character else ""
        char_reference = character.reference_url if character else None

        lock = SubjectLock(
            subject_type="product",
            reference_urls=urls,
            identity_features=identity_features,
            invariants=invariants,
            character_required=char_required,
            character_description=char_description,
            character_reference_url=char_reference,
        )
        lock.validate()
        return lock

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
