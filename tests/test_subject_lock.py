import pytest

from core.subject_lock import SubjectLockBuilder
from models.creative_plan import CharacterProfile, ProductProfile


def product():
    return ProductProfile(
        name="Serum X",
        category="skincare",
        description="Chai serum màu trắng",
        visual_identity=["chai trắng", "nhãn xanh", "logo X"],
        selling_points=["thiết kế tối giản"],
        consistency_requirements=["giữ nguyên logo", "không đổi màu chai"],
    )


def test_build_product_lock():
    lock = SubjectLockBuilder().build(
        ["https://example.com/front.jpg", "https://example.com/side.jpg"],
        product(),
    )

    assert lock.subject_type == "product"
    assert len(lock.reference_urls) == 2
    assert "chai trắng" in lock.identity_features
    assert "logo X" in lock.identity_features
    assert "giữ nguyên logo" in lock.invariants
    assert lock.character_required is False


def test_product_lock_has_default_invariants():
    lock = SubjectLockBuilder().build(
        ["https://example.com/product.jpg"],
        product(),
    )

    assert any("Không thay đổi hình dáng" in x for x in lock.invariants)
    assert any("physical object" in x for x in lock.invariants)


def test_character_lock_is_optional():
    character = CharacterProfile(
        required=True,
        description="Nữ 25 tuổi, tóc đen dài, phong cách tối giản",
        reference_url="https://example.com/person.jpg",
    )

    lock = SubjectLockBuilder().build(
        ["https://example.com/product.jpg"],
        product(),
        character,
    )

    assert lock.character_required is True
    assert lock.character_description.startswith("Nữ 25 tuổi")
    assert lock.character_reference_url.endswith("person.jpg")


def test_required_character_without_description_is_rejected():
    character = CharacterProfile(required=True, description="")

    with pytest.raises(ValueError, match="Character description"):
        SubjectLockBuilder().build(
            ["https://example.com/product.jpg"],
            product(),
            character,
        )


def test_empty_reference_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        SubjectLockBuilder().build([], product())


def test_empty_product_is_rejected():
    empty = ProductProfile()

    with pytest.raises(ValueError, match="ProductProfile"):
        SubjectLockBuilder().build(
            ["https://example.com/product.jpg"],
            empty,
        )
