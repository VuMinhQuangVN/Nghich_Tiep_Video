from pathlib import Path

from models.creative_plan import CreativeInput, CreativePlan, ProductProfile, CreativeConcept, VisualStyle, AudienceProfile, CharacterProfile, ScriptPlan, CreativeScene
from models.subject_lock import SubjectLock
from orchestrator.creative_pipeline_adapter import CreativePipelineAdapter
from techniques.base import BaseTechnique, TechniqueContext


def make_plan(refs):
    return CreativePlan(
        input=CreativeInput(list(refs), "sell", "tiktok", 10, "vi"),
        product=ProductProfile("Sản phẩm", "demo", "demo", ["logo", "shape"], [], ["keep logo"]),
        audience=AudienceProfile(),
        concept=CreativeConcept("Demo", "Demo", "Hook"),
        visual_style=VisualStyle("cinematic", "soft", [], "macro", "premium"),
        character=CharacterProfile(False, "", None),
        script=ScriptPlan("demo", [], "mua ngay"),
        scenes=[CreativeScene(1, description="show product", duration_sec=5)],
    )


def make_lock(refs):
    return SubjectLock(reference_urls=list(refs), identity_features=["logo"], invariants=["keep logo"])


def make_ctx(refs, character=None):
    return TechniqueContext(
        scenes=[CreativeScene(1, description="show product")],
        style="cinematic", subject_name="Sản phẩm", character_sheet_url=character,
        output_dir=Path("."), max_concurrent_image_requests=1,
        max_concurrent_video_submit=1, poll_interval_sec=1,
        product_reference_urls=list(refs),
    )


def test_adapter_forwards_all_product_references(tmp_path):
    refs = ["https://example.com/front.jpg", "https://example.com/back.jpg", "data:image/png;base64,AAA"]
    inp = CreativePipelineAdapter.to_pipeline_input(make_plan(refs), make_lock(refs), output_dir=tmp_path)
    assert inp.product_reference_url == refs[0]
    assert inp.product_reference_urls == refs


def test_reference_helper_returns_all_product_refs_and_character_sheet():
    refs = ["https://example.com/front.jpg", "https://example.com/back.jpg"]
    ctx = make_ctx(refs, "https://example.com/character.jpg")
    assert BaseTechnique.product_reference_images(ctx) == refs + ["https://example.com/character.jpg"]


def test_reference_helper_deduplicates_and_keeps_legacy_field():
    ctx = make_ctx([])
    ctx.product_reference_url = "https://example.com/legacy.jpg"
    assert BaseTechnique.product_reference_images(ctx) == [
        "https://example.com/legacy.jpg"
    ]


def test_reference_helper_deduplicates_multiple_refs():
    ctx = make_ctx([
        "https://example.com/front.jpg", "https://example.com/front.jpg",
        "https://example.com/back.jpg",
    ])
    assert BaseTechnique.product_reference_images(ctx) == [
        "https://example.com/front.jpg", "https://example.com/back.jpg"
    ]


def test_creative_plan_keeps_multiple_references():
    refs = ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"]
    plan = make_plan(refs)
    plan.validate()
    assert plan.input.product_reference_urls == refs
