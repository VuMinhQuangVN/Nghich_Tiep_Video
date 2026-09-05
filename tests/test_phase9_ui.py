from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX = PROJECT_ROOT / "static" / "index.html"


def _html() -> str:
    assert INDEX.exists(), f"Missing UI file: {INDEX}"
    return INDEX.read_text(encoding="utf-8")


def test_phase9_index_exists():
    assert INDEX.exists()
    assert INDEX.is_file()


def test_phase9_has_simple_and_advanced_mode_switch():
    html = _html()

    assert 'id="simpleModeBtn"' in html
    assert 'id="advancedModeBtn"' in html
    assert 'id="simplePane"' in html
    assert 'id="advancedPane"' in html


def test_phase9_simple_mode_has_required_inputs():
    html = _html()

    for field_id in (
        "simpleProductUrl",
        "simpleGoal",
        "simplePlatform",
        "simpleDuration",
    ):
        assert f'id="{field_id}"' in html


def test_phase9_simple_mode_has_expected_platforms():
    html = _html()

    for value in (
        "tiktok",
        "instagram_reels",
        "youtube_shorts",
        "facebook",
    ):
        assert f'value="{value}"' in html


def test_phase9_simple_mode_has_expected_durations():
    html = _html()

    for value in ("15", "30", "45", "60"):
        assert re.search(
            rf'<option\s+value="{value}"[^>]*>',
            html,
        )


def test_phase9_advanced_mode_has_pipeline_controls():
    html = _html()

    for field_id in (
        "script",
        "style",
        "subject",
        "keepCharacter",
        "reference",
        "quotaGroup",
        "advancedEngine",
        "advancedConcurrency",
    ):
        assert field_id in html


def test_phase9_mode_switch_toggles_active_panes():
    html = _html()

    assert "function setMode(mode)" in html
    assert "simplePane.classList.toggle('active', simple)" in html
    assert "advancedPane.classList.toggle('active', !simple)" in html
    assert "simpleModeBtn.addEventListener('click'" in html
    assert "advancedModeBtn.addEventListener('click'" in html


def test_phase9_simple_mode_calls_phase10_creative_generation_api():
    html = _html()

    assert "async function runSimpleCreativeJob()" in html
    assert "fetch('/api/creative-jobs'" in html
    assert "ProductAnalyzer" in html
    assert "CreativeDirector" in html
    assert "CreativePlan" in html
    assert "PipelineRunner" in html


def test_phase9_advanced_mode_keeps_current_job_api():
    html = _html()

    assert "async function runAdvancedJob()" in html
    assert "fetch('/api/jobs', { method: 'POST', body: fd })" in html
    assert "form.addEventListener('submit'" in html
