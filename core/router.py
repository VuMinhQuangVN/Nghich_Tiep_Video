"""
core/router.py
----------------
Router thuần: chọn technique dựa trên capability của engine và policy.

Phase 8 bổ sung:
- RouteDecision có reason + character_lock_required để caller biết vì sao route.
- Advanced developer override có validation capability; Simple Mode không cần dùng.
- Giữ choose_technique() làm API tương thích cho pipeline hiện tại.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from engines.base_engine import EngineCapabilities


class Technique(str, Enum):
    SINGLE_SHOT_DIRECT = "single_shot_direct"
    STORYBOARD_SHEET = "storyboard_sheet"
    FRAME_TO_FRAME_CHAIN = "frame_to_frame_chain"
    KEYFRAME_ARRAY = "keyframe_array"
    SCENE_EXTEND_EDIT = "scene_extend_edit"


class QuotaMode(str, Enum):
    SAVE = "tiết_kiệm"
    NORMAL = "bình_thường"


@dataclass(frozen=True)
class RouterInput:
    engine_capabilities: EngineCapabilities
    scene_count: int
    has_recurring_character: bool
    quota_mode: QuotaMode
    has_existing_video_to_fix: bool = False
    technique_override: Technique | None = None


@dataclass(frozen=True)
class RouteDecision:
    technique: Technique
    character_lock_required: bool
    reason: str
    overridden: bool = False


def _validate_input(inp: RouterInput) -> None:
    if not isinstance(inp.engine_capabilities, EngineCapabilities):
        raise TypeError("engine_capabilities phải là EngineCapabilities")
    if not isinstance(inp.scene_count, int) or isinstance(inp.scene_count, bool) or inp.scene_count < 1:
        raise ValueError("scene_count phải là số nguyên >= 1")
    if not isinstance(inp.has_recurring_character, bool):
        raise TypeError("has_recurring_character phải là bool")
    if not isinstance(inp.quota_mode, QuotaMode):
        raise TypeError("quota_mode phải là QuotaMode")
    if inp.technique_override is not None and not isinstance(inp.technique_override, Technique):
        raise TypeError("technique_override phải là Technique hoặc None")


def _supports(technique: Technique, cap: EngineCapabilities) -> bool:
    return {
        Technique.SINGLE_SHOT_DIRECT: cap.supports_image_to_video,
        Technique.STORYBOARD_SHEET: cap.supports_storyboard_read,
        Technique.FRAME_TO_FRAME_CHAIN: cap.supports_image_to_video,
        Technique.KEYFRAME_ARRAY: cap.supports_keyframe_array,
        Technique.SCENE_EXTEND_EDIT: cap.supports_edit,
    }[technique]


def route(inp: RouterInput) -> RouteDecision:
    """Áp dụng decision table theo đúng thứ tự ưu tiên của knowledge-base."""
    _validate_input(inp)
    cap = inp.engine_capabilities

    # Advanced override chỉ được phép khi technique thực sự được engine hỗ trợ.
    if inp.technique_override is not None:
        if not _supports(inp.technique_override, cap):
            raise ValueError(
                f"Technique override '{inp.technique_override.value}' không được engine hỗ trợ"
            )
        return RouteDecision(
            technique=inp.technique_override,
            character_lock_required=inp.has_recurring_character,
            reason="Developer override đã được yêu cầu và capability đã được kiểm tra.",
            overridden=True,
        )

    # LUẬT 0 — character lock là prerequisite, không thay đổi technique.
    character_lock_required = inp.has_recurring_character

    # LUẬT 1 — sửa video có sẵn.
    if inp.has_existing_video_to_fix:
        if cap.supports_edit:
            return RouteDecision(
                Technique.SCENE_EXTEND_EDIT,
                character_lock_required,
                "Đang sửa video có sẵn và engine hỗ trợ edit.",
            )
        return RouteDecision(
            Technique.FRAME_TO_FRAME_CHAIN,
            character_lock_required,
            "Đang sửa video có sẵn nhưng engine không hỗ trợ edit; fallback chaining.",
        )

    # LUẬT 2 — một scene.
    if inp.scene_count == 1:
        return RouteDecision(
            Technique.SINGLE_SHOT_DIRECT,
            character_lock_required,
            "Chỉ có 1 scene; dùng direct để tránh over-engineer.",
        )

    # LUẬT 3 — engine hiểu storyboard.
    if cap.supports_storyboard_read:
        if inp.quota_mode == QuotaMode.SAVE:
            return RouteDecision(
                Technique.STORYBOARD_SHEET,
                character_lock_required,
                "Nhiều scene + storyboard support + ưu tiên tiết kiệm quota.",
            )
        return RouteDecision(
            Technique.FRAME_TO_FRAME_CHAIN,
            character_lock_required,
            "Nhiều scene + storyboard support nhưng ưu tiên kiểm soát từng scene.",
        )

    # LUẬT 3B — engine hỗ trợ keyframe array.
    if cap.supports_keyframe_array:
        if inp.quota_mode == QuotaMode.SAVE:
            return RouteDecision(
                Technique.KEYFRAME_ARRAY,
                character_lock_required,
                "Nhiều scene + keyframe-array support + ưu tiên tiết kiệm quota.",
            )
        return RouteDecision(
            Technique.FRAME_TO_FRAME_CHAIN,
            character_lock_required,
            "Nhiều scene + keyframe-array support nhưng ưu tiên kiểm soát từng scene.",
        )

    # LUẬT 4 — fallback an toàn.
    return RouteDecision(
        Technique.FRAME_TO_FRAME_CHAIN,
        character_lock_required,
        "Engine không hỗ trợ storyboard/keyframe-array; dùng fallback chaining.",
    )


def choose_technique(inp: RouterInput) -> Technique:
    """Backward-compatible API: chỉ trả technique như trước Phase 8."""
    return route(inp).technique
