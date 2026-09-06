import json
from pathlib import Path

import pytest

from engines.base_engine import EngineCapabilities, ImageResult, VideoStatus, VideoTaskHandle
from models.creative_plan import (
    CharacterProfile, CreativeConcept, CreativeInput, CreativePlan,
    ProductProfile, ScriptPlan, VisualStyle,
)
from models.subject_lock import SubjectLock
from orchestrator.pipeline_runner import PipelineInput, PipelineRunner
from core.router import QuotaMode


class FakeEngine:
    capabilities = EngineCapabilities(
        supports_keyframe_array=True,
        supports_image_to_video=True,
    )

    def __init__(self, scene_response, shot_response):
        self.scene_response = scene_response
        self.shot_response = shot_response
        self.plan_calls = []
        self.image_prompts = []
        self.video_prompts = []

    async def analyze_image(self, image_path_or_url, question):
        raise AssertionError("wiring test must not call analyze_image")

    async def plan_scenes(self, script_text, style_hint=""):
        self.plan_calls.append((script_text, style_hint))
        return self.scene_response if len(self.plan_calls) == 1 else self.shot_response

    async def generate_image(self, prompt, ratio="9:16", size="2K", reference_images=None):
        self.image_prompts.append((prompt, reference_images))
        return ImageResult(f"image-{len(self.image_prompts)}.png")

    async def submit_video_task(self, prompt, images=None, mode="ti2vid", num_frames=121, frame_rate=24, negative_prompt=None):
        self.video_prompts.append((prompt, images, mode))
        return "video-1"

    async def poll_video_task(self, video_id):
        return VideoTaskHandle(video_id=video_id, status=VideoStatus.COMPLETED, result_url="https://example.com/video.mp4")

    async def download_video(self, video_url, dest_path):
        Path(dest_path).write_bytes(b"fake mp4")
        return dest_path


def make_plan():
    return CreativePlan(
        input=CreativeInput([
            "https://example.com/product-front.jpg",
            "https://example.com/product-back.jpg",
        ], "sell", "tiktok", 5, "vi"),
        product=ProductProfile(
            "Serum X", "skincare", "White serum bottle",
            ["white bottle", "blue label"], ["minimal design"], ["keep logo"],
        ),
        concept=CreativeConcept("Reveal", "Clean product reveal", "Stop scrolling"),
        visual_style=VisualStyle("premium", "soft", ["white", "blue"], "macro", "fresh"),
        character=CharacterProfile(False, "", None),
        script=ScriptPlan("Serum X", ["Try it"], "Shop now"),
    )


def make_lock():
    return SubjectLock(
        reference_urls=[
            "https://example.com/product-front.jpg",
            "https://example.com/product-back.jpg",
        ],
        identity_features=["white bottle", "blue label"],
        invariants=["keep logo"],
    )


def scene_response():
    return json.dumps([{
        "index": 1,
        "objective": "Hook product",
        "description": "Hero reveal of Serum X",
        "duration_sec": 5,
        "camera": "macro",
        "camera_motion": "slow push-in",
        "framing": "close-up",
        "product_visibility": "fully visible",
        "product_position": "center",
        "character_action": "",
        "environment": "clean studio",
        "lighting": "soft",
        "mood": "fresh",
        "transition": "cut",
        "voiceover": "Serum X",
        "text_overlay": "",
        "cta": "Shop now",
    }])


def shot_response():
    return json.dumps([{
        "index": 1,
        "shot_type": "hero product shot",
        "framing": "close-up",
        "camera_angle": "eye level",
        "camera_motion": "slow push-in",
        "subject_position": "center frame",
        "action": "product remains still",
        "environment": "clean studio",
        "lighting": "soft key light",
        "duration_sec": 5,
        "generation_prompt": "draft hero shot",
    }])


@pytest.mark.asyncio
async def test_phase6_and_7_are_wired_before_technique(tmp_path):
    engine = FakeEngine(scene_response(), shot_response())
    plan = make_plan()
    lock = make_lock()
    inp = PipelineInput(
        script_text="legacy not used",
        style_hint="premium",
        subject_name="Serum X",
        reference_image_url=None,
        keep_character_consistent=False,
        quota_mode=QuotaMode.SAVE,
        max_concurrent_image_requests=1,
        max_concurrent_video_submit=1,
        poll_interval_sec=0,
        output_dir=tmp_path,
        product_reference_url="https://example.com/product-front.jpg",
        product_reference_urls=[
            "https://example.com/product-front.jpg",
            "https://example.com/product-back.jpg",
        ],
        creative_plan=plan,
        subject_lock=lock,
    )

    result = await PipelineRunner(engine).run(inp)

    assert result.final_video_path.exists()
    assert len(engine.plan_calls) == 2  # ScenePlanner + ShotPlanner
    assert len(engine.image_prompts) == 1
    image_prompt = engine.image_prompts[0][0]
    image_refs = engine.image_prompts[0][1]
    assert image_refs == [
        "https://example.com/product-front.jpg",
        "https://example.com/product-back.jpg",
    ]
    assert "GLOBAL CONSISTENCY" in image_prompt
    assert "PRODUCT CONSISTENCY" in image_prompt
    assert "Serum X" in image_prompt
    assert "Hero reveal of Serum X" in image_prompt
    assert "slow push-in" in image_prompt
    assert len(engine.video_prompts) == 1
    assert "GLOBAL CONSISTENCY" in engine.video_prompts[0][0]
    assert "SHOT DESCRIPTION" in engine.video_prompts[0][0]
    assert "NEGATIVE CONSTRAINTS" in engine.video_prompts[0][0]
