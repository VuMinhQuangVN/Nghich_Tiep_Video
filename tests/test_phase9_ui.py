from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_has_simple_and_advanced_modes():
    assert 'id="simpleModeBtn"' in HTML
    assert 'id="advancedModeBtn"' in HTML
    assert 'id="simplePanel"' in HTML
    assert 'id="advancedPanel"' in HTML


def test_simple_mode_matches_phase9_brief_inputs():
    for element_id in ("simpleProduct", "goal", "platform", "duration", "simpleBrief"):
        assert f'id="{element_id}"' in HTML
    assert "TẠO VIDEO" in HTML


def test_simple_mode_hides_developer_controls():
    assert 'class="step advanced-only show"' in HTML
    assert "Developer Overrides" in HTML
    assert "techniqueOverride" in HTML
    assert "concurrency" in HTML
    assert "engine" in HTML


def test_advanced_mode_contains_requested_controls():
    for label in ("Script", "Style", "Character / Subject", "Reference URL", "Technique", "Concurrency", "Engine"):
        assert label in HTML


def test_simple_mode_does_not_expose_technique_selector():
    simple_section = HTML.split('<section id="simplePanel">', 1)[1].split('<section id="advancedPanel"', 1)[0]
    assert "techniqueOverride" not in simple_section
    assert "Concurrency" not in simple_section
    assert "Engine" not in simple_section


def test_simple_brief_is_converted_to_existing_pipeline_script():
    assert "function simpleBriefToScript()" in HTML
    assert "Target duration:" in HTML
    assert "Platform:" in HTML
    assert "Create a coherent product-video script and scene plan" in HTML


def test_mode_switch_updates_required_fields():
    assert "document.getElementById('simpleBrief').required=simple" in HTML
    assert "document.getElementById('script').required=!simple" in HTML


def test_phase9_keeps_generation_endpoint_unchanged():
    # Phase 9 is UI-only: the existing job endpoint remains the generation boundary.
    server = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert '@app.post("/api/jobs")' in server
    assert "start_job(" in server
