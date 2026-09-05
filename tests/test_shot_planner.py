import json

import pytest

from core.shot_planner import ShotPlanner
from models.creative_plan import (
    CharacterProfile,
    CreativeInput,
    CreativePlan,
    CreativeScene,
    ProductProfile,
    VisualStyle,
)
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock


class FakeEngine:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def plan_scenes(self, script_text, style_hint=""):
        self.calls.append((script_text, style_hint))
        return self.response


def make_plan(character=False):
    return CreativePlan(
        input=CreativeInput(
            product_reference_urls=["https://example.com/product.jpg"],
            goal="Tăng nhận diện sản phẩm",
            platform="TikTok",
            duration_sec=10,
        ),
        product=ProductProfile(name="Serum X", category="serum"),
        visual_style=VisualStyle(style="premium clean", lighting="soft", mood="fresh"),
        character=CharacterProfile(required=character, description="Nữ mẫu tóc dài" if character else ""),
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
    )


def make_lock(character=False):
    return SubjectLock(
        subject_type="product",
        reference_urls=["https://example.com/product.jpg"],
        identity_features=["logo", "packaging", "color"],
        invariants=["Giữ nguyên nhận diện sản phẩm"],
        character_required=character,
        character_description="Nữ mẫu tóc dài" if character else "",
    )


def response():
    return json.dumps([
        {
            "index": 1,
            "shot_type": "macro product shot",
            "framing": "extreme close-up",
            "camera_angle": "eye level",
            "camera_motion": "slow push-in",
            "subject_position": "center frame",
            "action": "product remains still",
            "environment": "clean studio",
            "lighting": "soft studio light",
            "duration_sec": 2,
            "generation_prompt": "macro hero shot of the approved product",
        },
        {
            "index": 2,
            "shot_type": "hero shot",
            "framing": "close-up",
            "camera_angle": "slight low angle",
            "camera_motion": "slow orbit",
            "subject_position": "center frame",
            "action": "product remains still",
            "environment": "clean studio",
            "lighting": "soft studio light",
            "duration_sec": 3,
            "generation_prompt": "premium hero view of the approved product",
        },
    ])


@pytest.mark.asyncio
async def test_plans_one_scene_into_structured_shots():
    engine = FakeEngine(response())
    shots = await ShotPlanner(engine).plan_scene(make_scene(), make_plan(), make_lock())

    assert len(shots) == 2
    assert all(isinstance(shot, CreativeShot) for shot in shots)
    assert shots[0].shot_type == "macro product shot"
    assert sum(shot.duration_sec for shot in shots) == 5
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_prompt_contains_scene_and_subject_lock():
    engine = FakeEngine(response())
    await ShotPlanner(engine).plan_scene(make_scene(), make_plan(), make_lock())
    prompt = engine.calls[0][0]

    assert "Hero reveal" in prompt
    assert "Giữ nguyên nhận diện sản phẩm" in prompt
    assert "Serum X" in prompt


@pytest.mark.asyncio
async def test_rejects_character_action_when_character_lock_disabled():
    bad = json.dumps([{**json.loads(response())[0], "action": "woman holds the product"}])
    with pytest.raises(ValueError, match="character action"):
        await ShotPlanner(FakeEngine(bad)).plan_scene(make_scene(), make_plan(), make_lock())


@pytest.mark.asyncio
async def test_requires_matching_character_state():
    with pytest.raises(ValueError, match="character state"):
        await ShotPlanner(FakeEngine(response())).plan_scene(
            make_scene(character=True), make_plan(character=True), make_lock(False)
        )


@pytest.mark.asyncio
async def test_rejects_non_sequential_shot_indexes():
    bad = json.dumps([{**json.loads(response())[0], "index": 2}])
    with pytest.raises(ValueError, match="sequential"):
        await ShotPlanner(FakeEngine(bad)).plan_scene(make_scene(), make_plan(), make_lock())


@pytest.mark.asyncio
async def test_rejects_duration_over_scene_budget():
    bad = json.dumps([
        {**json.loads(response())[0], "duration_sec": 4},
        {**json.loads(response())[1], "duration_sec": 3},
    ])
    with pytest.raises(ValueError, match="25%"):
        await ShotPlanner(FakeEngine(bad)).plan_scene(make_scene(), make_plan(), make_lock())


@pytest.mark.asyncio
async def test_rejects_missing_camera_fields():
    bad_item = json.loads(response())[0]
    bad_item["camera_motion"] = ""
    with pytest.raises(ValueError, match="camera_motion"):
        await ShotPlanner(FakeEngine(json.dumps([bad_item]))).plan_scene(
            make_scene(), make_plan(), make_lock()
        )


@pytest.mark.asyncio
async def test_rejects_invalid_json():
    with pytest.raises(ValueError, match="valid JSON array"):
        await ShotPlanner(FakeEngine("not json")).plan_scene(make_scene(), make_plan(), make_lock())


@pytest.mark.asyncio
async def test_parses_fenced_json():
    fenced = "```json\n" + response() + "\n```"
    shots = await ShotPlanner(FakeEngine(fenced)).plan_scene(make_scene(), make_plan(), make_lock())
    assert len(shots) == 2


@pytest.mark.asyncio
async def test_plans_multiple_scenes_sequentially():
    scene2 = make_scene()
    scene2.index = 2
    scene2.description = "Cận cảnh chi tiết sản phẩm"
    scene2.duration_sec = 4

    engine = FakeEngine(response())
    result = await ShotPlanner(engine).plan([make_scene(), scene2], make_plan(), make_lock())

    assert list(result) == [1, 2]
    assert len(engine.calls) == 2
