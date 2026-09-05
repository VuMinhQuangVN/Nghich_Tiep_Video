import pytest

from core.router import QuotaMode, RouteDecision, RouterInput, Technique, choose_technique, route
from engines.base_engine import EngineCapabilities


def caps(**kwargs):
    return EngineCapabilities(**kwargs)


def test_single_scene_wins():
    inp = RouterInput(caps(supports_keyframe_array=True), 1, False, QuotaMode.NORMAL)
    assert choose_technique(inp) == Technique.SINGLE_SHOT_DIRECT


def test_storyboard_save():
    inp = RouterInput(caps(supports_storyboard_read=True), 3, False, QuotaMode.SAVE)
    assert choose_technique(inp) == Technique.STORYBOARD_SHEET


def test_storyboard_normal_uses_chain():
    inp = RouterInput(caps(supports_storyboard_read=True), 3, False, QuotaMode.NORMAL)
    assert choose_technique(inp) == Technique.FRAME_TO_FRAME_CHAIN


def test_keyframe_save():
    inp = RouterInput(caps(supports_keyframe_array=True), 3, False, QuotaMode.SAVE)
    assert choose_technique(inp) == Technique.KEYFRAME_ARRAY


def test_keyframe_normal_uses_chain():
    inp = RouterInput(caps(supports_keyframe_array=True), 3, False, QuotaMode.NORMAL)
    assert choose_technique(inp) == Technique.FRAME_TO_FRAME_CHAIN


def test_basic_engine_fallback():
    inp = RouterInput(caps(), 3, False, QuotaMode.SAVE)
    assert choose_technique(inp) == Technique.FRAME_TO_FRAME_CHAIN


def test_edit_rule_has_priority():
    inp = RouterInput(caps(supports_edit=True), 1, False, QuotaMode.SAVE, True)
    assert choose_technique(inp) == Technique.SCENE_EXTEND_EDIT


def test_edit_without_support_falls_back_to_chain():
    inp = RouterInput(caps(), 1, False, QuotaMode.SAVE, True)
    assert choose_technique(inp) == Technique.FRAME_TO_FRAME_CHAIN


def test_character_lock_is_metadata_not_technique_override():
    decision = route(RouterInput(caps(supports_keyframe_array=True), 2, True, QuotaMode.SAVE))
    assert decision.technique == Technique.KEYFRAME_ARRAY
    assert decision.character_lock_required is True


def test_route_exposes_reason():
    decision = route(RouterInput(caps(supports_keyframe_array=True), 2, False, QuotaMode.SAVE))
    assert isinstance(decision, RouteDecision)
    assert "keyframe" in decision.reason.lower()
    assert decision.overridden is False


def test_override_supported_technique():
    decision = route(
        RouterInput(
            caps(supports_keyframe_array=True),
            3,
            False,
            QuotaMode.NORMAL,
            technique_override=Technique.KEYFRAME_ARRAY,
        )
    )
    assert decision.technique == Technique.KEYFRAME_ARRAY
    assert decision.overridden is True


def test_override_rejects_unsupported_technique():
    with pytest.raises(ValueError, match="không được engine hỗ trợ"):
        route(
            RouterInput(
                caps(supports_keyframe_array=True),
                3,
                False,
                QuotaMode.NORMAL,
                technique_override=Technique.STORYBOARD_SHEET,
            )
        )


@pytest.mark.parametrize("scene_count", [0, -1])
def test_invalid_scene_count(scene_count):
    with pytest.raises(ValueError):
        route(RouterInput(caps(), scene_count, False, QuotaMode.NORMAL))


def test_invalid_quota_mode():
    with pytest.raises(TypeError):
        route(RouterInput(caps(), 2, False, "save"))
