from pathlib import Path

import pytest

from core.router import QuotaMode
from models.creative_plan import (
    AudienceProfile, CharacterProfile, CreativeConcept, CreativeInput,
    CreativePlan, ProductProfile, ScriptPlan, VisualStyle,
)
from models.subject_lock import SubjectLock
from orchestrator.creative_pipeline_adapter import CreativePipelineAdapter


def make_plan() -> CreativePlan:
    return CreativePlan(
        input=CreativeInput(["https://example.com/product.jpg"], "sell", "tiktok", 15, "vi"),
        product=ProductProfile(
            "Serum X", "skincare", "White serum bottle",
            ["white bottle", "blue label"], ["minimal design"], ["keep logo"],
        ),
        audience=AudienceProfile("18-30", "female", ["skincare"], []),
        concept=CreativeConcept("Reveal", "Clean product reveal", "3 giây đầu"),
        visual_style=VisualStyle("premium", "soft", ["white", "blue"], "macro", "fresh"),
        character=CharacterProfile(False, "", None),
        script=ScriptPlan("Đây là Serum X.", ["Clean beauty"], "Khám phá ngay"),
    )


def make_lock() -> SubjectLock:
    return SubjectLock(
        reference_urls=["https://example.com/product.jpg"],
        identity_features=["white bottle", "blue label"],
        invariants=["keep logo"],
    )


def test_adapter_maps_creative_plan_to_pipeline_input(tmp_path):
    plan = make_plan()
    inp = CreativePipelineAdapter.to_pipeline_input(plan, make_lock(), output_dir=tmp_path)
    assert inp.script_text.startswith("HOOK: 3 giây đầu")
    assert "VOICEOVER: Đây là Serum X." in inp.script_text
    assert "CTA: Khám phá ngay" in inp.script_text
    assert inp.style_hint == "premium, soft, macro, fresh, color palette: white, blue"
    assert inp.subject_name == "Serum X"
    assert inp.product_reference_url == "https://example.com/product.jpg"
    assert inp.creative_plan is plan
    assert inp.subject_lock is not None


def test_adapter_preserves_runtime_settings(tmp_path):
    inp = CreativePipelineAdapter.to_pipeline_input(
        make_plan(), make_lock(), output_dir=tmp_path,
        quota_mode=QuotaMode.NORMAL,
        max_concurrent_image_requests=2,
        max_concurrent_video_submit=3,
        poll_interval_sec=7,
    )
    assert inp.quota_mode is QuotaMode.NORMAL
    assert inp.max_concurrent_image_requests == 2
    assert inp.max_concurrent_video_submit == 3
    assert inp.poll_interval_sec == 7


def test_adapter_requires_subject_lock(tmp_path):
    with pytest.raises(TypeError, match="SubjectLock"):
        CreativePipelineAdapter.to_pipeline_input(make_plan(), None, output_dir=tmp_path)


def test_adapter_rejects_empty_creative_content(tmp_path):
    plan = make_plan()
    plan.script.voiceover = ""
    plan.script.text_overlays = []
    plan.script.cta = ""
    plan.concept.hook = ""
    plan.concept.description = ""
    with pytest.raises(ValueError, match="script/concept"):
        CreativePipelineAdapter.to_pipeline_input(plan, make_lock(), output_dir=tmp_path)


def test_pipeline_input_keeps_legacy_and_phase10_fields(tmp_path):
    inp = CreativePipelineAdapter.to_pipeline_input(make_plan(), make_lock(), output_dir=tmp_path)
    assert isinstance(inp.output_dir, Path)
    assert inp.reference_image_url is None
    assert inp.keep_character_consistent is False
