import pytest

from core.prompt_composer import PromptComposer
from models.creative_plan import (
    CharacterProfile,
    CreativeConcept,
    CreativeInput,
    CreativePlan,
    CreativeScene,
    ProductProfile,
    VisualStyle,
)
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock


def make_plan(character=False):
    return CreativePlan(
        input=CreativeInput(
            product_reference_urls=["https://example.com/product.jpg"],
            goal="Tăng nhận diện sản phẩm",
            platform="TikTok",
            duration_sec=10,
        ),
        product=ProductProfile(
            name="Serum X",
            category="serum",
            description="Chai serum thủy tinh tối màu",
            visual_identity=["chai thủy tinh tối màu", "logo trắng"],
            selling_points=["kết cấu nhẹ"],
        ),
        concept=CreativeConcept(title="Premium reveal", description="Hero reveal", hook="Reveal"),
        visual_style=VisualStyle(
            style="premium clean",
            lighting="soft studio",
            color_palette=["black", "white"],
            camera_style="cinematic",
            mood="fresh",
        ),
        character=CharacterProfile(
            required=character,
            description="Nữ mẫu tóc dài" if character else "",
        ),
    )


def make_scene(character=False):
    return CreativeScene(
        index=1,
        objective="Giới thiệu sản phẩm",
        description="Hero reveal của sản phẩm trên nền studio sạch",
        duration_sec=5,
        camera="product camera",
        camera_motion="slow push-in",
        framing="medium close-up",
        product_visibility="fully visible",
        product_position="center",
        character_action="Cầm sản phẩm" if character else "",
        environment="clean studio",
        lighting="soft studio",
        mood="premium",
        transition="cut",
    )


def make_shot():
    return CreativeShot(
        index=1,
        shot_type="hero shot",
        framing="close-up",
        camera_angle="slight low angle",
        camera_motion="slow orbit",
        subject_position="center frame",
        action="product remains still",
        environment="clean studio",
        lighting="soft key light",
        duration_sec=4,
        generation_prompt="draft hero shot",
    )


def make_lock(character=False):
    return SubjectLock(
        reference_urls=["https://example.com/product.jpg"],
        identity_features=["logo", "packaging", "color"],
        invariants=["Giữ nguyên nhận diện sản phẩm"],
        character_required=character,
        character_description="Nữ mẫu tóc dài" if character else "",
    )


def test_composes_final_prompt_from_all_layers():
    prompt = PromptComposer().compose_shot_prompt(
        make_plan(), make_lock(), make_scene(), make_shot()
    )

    for expected in (
        "GLOBAL CONSISTENCY",
        "PRODUCT CONSISTENCY",
        "CHARACTER CONSISTENCY",
        "SHOT DESCRIPTION",
        "CAMERA",
        "LIGHTING",
        "MOTION",
        "NEGATIVE CONSTRAINTS",
        "Serum X",
        "chai thủy tinh tối màu",
        "premium clean",
        "Hero reveal của sản phẩm",
        "slow orbit",
        "soft key light",
    ):
        assert expected in prompt


def test_product_invariants_are_present_as_negative_constraints():
    prompt = PromptComposer().compose(make_plan(), make_lock(), make_scene(), make_shot())
    assert "Giữ nguyên nhận diện sản phẩm" in prompt
    assert "Do not change logo, packaging, shape, color" in prompt
    assert "Do not invent unsupported product features" in prompt


def test_does_not_introduce_character_when_lock_disabled():
    scene = make_scene()
    scene.character_action = "A woman holds the product"
    with pytest.raises(ValueError, match="character"):
        PromptComposer().compose(make_plan(False), make_lock(False), scene, make_shot())


def test_character_identity_is_composed_when_enabled():
    prompt = PromptComposer().compose(
        make_plan(True), make_lock(True), make_scene(True), make_shot()
    )
    assert "Nữ mẫu tóc dài" in prompt
    assert "Do not change the locked character identity" in prompt


def test_plan_and_lock_character_state_must_match():
    with pytest.raises(ValueError, match="character state"):
        PromptComposer().compose(make_plan(True), make_lock(False), make_scene(True), make_shot())


def test_rejects_wrong_types():
    with pytest.raises(TypeError, match="CreativePlan"):
        PromptComposer().compose("bad", make_lock(), make_scene(), make_shot())
