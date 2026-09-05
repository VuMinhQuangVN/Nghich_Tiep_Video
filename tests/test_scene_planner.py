import pytest

from core.scene_planner import ScenePlanner
from models.creative_plan import (
    AudienceProfile,
    CharacterProfile,
    CreativeConcept,
    CreativeInput,
    CreativePlan,
    ProductProfile,
    ScriptPlan,
    VisualStyle,
)
from models.subject_lock import SubjectLock


class FakeEngine:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def plan_scenes(self, script_text, style_hint=""):
        self.calls.append((script_text, style_hint))
        return self.response


def plan(character_required=False):
    return CreativePlan(
        input=CreativeInput(
            ["https://example.com/serum.jpg"],
            "Tăng nhận diện và thúc đẩy mua hàng",
            "TikTok",
            15,
            "vi",
        ),
        product=ProductProfile(
            "Serum X", "skincare", "Chai serum màu trắng",
            ["chai trắng", "nhãn xanh", "logo X"],
            ["thiết kế tối giản"],
            ["giữ nguyên logo", "không đổi màu chai"],
        ),
        audience=AudienceProfile("18-30", "female", ["skincare"], ["khó chọn serum"]),
        concept=CreativeConcept("Một giây nhận ra", "Reveal nhanh sản phẩm", "Bạn có 3 giây?"),
        visual_style=VisualStyle("premium clean beauty", "soft studio", ["white", "blue"], "macro", "fresh"),
        character=CharacterProfile(character_required, "Nữ 25 tuổi" if character_required else "", None),
        script=ScriptPlan("Đây là Serum X.", ["Clean beauty"], "Khám phá ngay"),
    )


def lock(character_required=False):
    return SubjectLock(
        reference_urls=["https://example.com/serum.jpg"],
        identity_features=["chai trắng", "nhãn xanh", "logo X"],
        invariants=["giữ nguyên logo", "không đổi màu chai"],
        character_required=character_required,
        character_description="Nữ 25 tuổi" if character_required else "",
    )


RESPONSE = [
    {
        "index": 1,
        "objective": "Hook và giới thiệu sản phẩm",
        "description": "Hero shot của Serum X trên nền studio sạch",
        "duration_sec": 4,
        "camera": "Close-up",
        "camera_motion": "Slow push-in",
        "framing": "Product close-up",
        "product_visibility": "Rõ ràng, chiếm khung hình chính",
        "product_position": "Trung tâm",
        "character_action": "",
        "environment": "Premium studio",
        "lighting": "Soft beauty lighting",
        "mood": "Fresh",
        "transition": "Cut",
        "voiceover": "Đây là Serum X.",
        "text_overlay": "Clean beauty",
        "cta": "",
    },
    {
        "index": 2,
        "objective": "Tạo cảm giác tin cậy về thiết kế",
        "description": "Cận cảnh chai serum và nhãn sản phẩm",
        "duration_sec": 5,
        "camera": "Macro",
        "camera_motion": "Slow lateral move",
        "framing": "Macro",
        "product_visibility": "Toàn bộ thân chai và nhãn rõ nét",
        "product_position": "Lệch phải",
        "character_action": "",
        "environment": "Studio",
        "lighting": "Soft studio",
        "mood": "Premium",
        "transition": "Match cut",
        "voiceover": "",
        "text_overlay": "",
        "cta": "",
    },
]


@pytest.mark.asyncio
async def test_phase5_builds_structured_scenes_from_plan_and_lock():
    engine = FakeEngine(RESPONSE)
    scenes = await ScenePlanner(engine).plan_creative(plan(), lock())

    assert len(scenes) == 2
    assert scenes[0].objective == "Hook và giới thiệu sản phẩm"
    assert scenes[0].camera == "Close-up"
    assert scenes[0].camera_motion == "Slow push-in"
    assert scenes[0].product_visibility.startswith("Rõ ràng")
    assert scenes[0].voiceover == "Đây là Serum X."
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_prompt_contains_creative_plan_and_lock_contract():
    engine = FakeEngine(RESPONSE)
    await ScenePlanner(engine).plan_creative(plan(), lock())
    prompt, style = engine.calls[0]

    assert "Scene Planner 2.0" in prompt
    assert "Một giây nhận ra" in prompt
    assert "premium clean beauty" in prompt
    assert "logo X" in prompt
    assert "giữ nguyên logo" in prompt
    assert "Không tạo SHOT" in prompt
    assert style == ""


@pytest.mark.asyncio
async def test_character_action_is_rejected_when_character_lock_is_off():
    bad = [dict(RESPONSE[0], character_action="Cầm sản phẩm")]
    with pytest.raises(ValueError, match="character_action"):
        await ScenePlanner(FakeEngine(bad)).plan_creative(plan(False), lock(False))


@pytest.mark.asyncio
async def test_character_lock_requires_matching_creative_plan():
    with pytest.raises(ValueError, match="character"):
        await ScenePlanner(FakeEngine(RESPONSE)).plan(plan(False), lock(True))


@pytest.mark.asyncio
async def test_missing_required_scene_field_is_rejected():
    bad = [dict(RESPONSE[0], product_visibility="")]
    with pytest.raises(ValueError, match="product_visibility"):
        await ScenePlanner(FakeEngine(bad)).plan_creative(plan(), lock())


@pytest.mark.asyncio
async def test_non_sequential_indexes_are_rejected():
    bad = [dict(RESPONSE[0], index=2)]
    with pytest.raises(ValueError, match="sequential"):
        await ScenePlanner(FakeEngine(bad)).plan_creative(plan(), lock())


@pytest.mark.asyncio
async def test_duration_over_budget_is_rejected():
    bad = [dict(RESPONSE[0], duration_sec=20)]
    with pytest.raises(ValueError, match="25%"):
        await ScenePlanner(FakeEngine(bad)).plan_creative(plan(), lock())


@pytest.mark.asyncio
async def test_invalid_json_is_rejected():
    with pytest.raises(ValueError, match="JSON array"):
        await ScenePlanner(FakeEngine("not json")).plan_creative(plan(), lock())


def test_parse_markdown_json_array():
    raw = "```json\n" + str(RESPONSE).replace("'", '"') + "\n```"
    parsed = ScenePlanner._parse_response(raw)
    assert parsed[0]["index"] == 1


@pytest.mark.asyncio
async def test_legacy_adapter_keeps_old_engine_contract():
    old = [{"index": 1, "description": "Hero", "duration_sec": 4, "camera_move": "push in"}]
    scenes = await ScenePlanner(FakeEngine(old)).plan_legacy("script", "style")
    assert scenes[0].description == "Hero"
    assert scenes[0].camera_motion == "push in"
