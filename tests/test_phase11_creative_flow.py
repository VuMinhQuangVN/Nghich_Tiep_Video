import asyncio
from pathlib import Path

from models.creative_plan import CreativeInput, CreativePlan, CreativeScene, CreativeConcept, ScriptPlan
from orchestrator.creative_pipeline_adapter import CreativePipelineAdapter


def test_creative_plan_builds_post_processing_options():
    plan = CreativePlan(
        input=CreativeInput(
            product_reference_urls=["https://example.com/product.jpg"],
            goal="sell",
            platform="tiktok",
            duration_sec=10,
        ),
        concept=CreativeConcept(hook="Hook"),
        script=ScriptPlan(text_overlays=["fallback overlay"], cta="Mua ngay"),
        scenes=[
            CreativeScene(index=1, duration_sec=5, text_overlay="Scene text"),
            CreativeScene(index=2, duration_sec=5),
        ],
    )

    options = CreativePipelineAdapter.to_post_process_options(
        plan,
        voiceover_path=Path("voice.wav"),
        background_music_path=Path("music.mp3"),
        subtitles_path=Path("captions.srt"),
    )

    assert options.voiceover_path == Path("voice.wav")
    assert options.background_music_path == Path("music.mp3")
    assert options.subtitles_path == Path("captions.srt")
    assert [x.text for x in options.text_overlays] == ["Scene text"]
    assert options.cta == "Mua ngay"


def test_creative_plan_post_processing_is_noop_when_no_optional_input():
    plan = CreativePlan(
        input=CreativeInput(
            product_reference_urls=["https://example.com/product.jpg"],
            goal="sell",
            platform="tiktok",
            duration_sec=10,
        ),
        scenes=[CreativeScene(index=1, duration_sec=10)],
    )
    options = CreativePipelineAdapter.to_post_process_options(plan)
    assert not options.voiceover_path
    assert not options.background_music_path
    assert not options.subtitles_path
    assert not options.text_overlays
    assert options.cta is None
