"""
core/router.py
----------------
Implement Y NGUYÊN logic trong knowledge-base/router.md dưới dạng hàm thuần
(pure function) — không side-effect, dễ unit test độc lập.

Luật đọc từ trên xuống, luật đầu tiên khớp thì dừng (giống bảng quyết định
trong router.md).
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


@dataclass
class RouterInput:
    engine_capabilities: EngineCapabilities
    scene_count: int
    has_recurring_character: bool
    quota_mode: QuotaMode
    has_existing_video_to_fix: bool = False


def choose_technique(inp: RouterInput) -> Technique:
    cap = inp.engine_capabilities

    # LUẬT 1 — sửa video có sẵn
    if inp.has_existing_video_to_fix:
        if cap.supports_edit:
            return Technique.SCENE_EXTEND_EDIT
        return Technique.FRAME_TO_FRAME_CHAIN

    # LUẬT 2 — chỉ 1 scene
    if inp.scene_count == 1:
        return Technique.SINGLE_SHOT_DIRECT

    # LUẬT 3 — nhiều scene, engine hiểu storyboard
    if inp.scene_count >= 2 and cap.supports_storyboard_read:
        if inp.quota_mode == QuotaMode.SAVE:
            return Technique.STORYBOARD_SHEET
        return Technique.FRAME_TO_FRAME_CHAIN

    # LUẬT 3B — nhiều scene, engine hỗ trợ keyframe array (VD: Agnes)
    if inp.scene_count >= 2 and cap.supports_keyframe_array:
        if inp.quota_mode == QuotaMode.SAVE:
            return Technique.KEYFRAME_ARRAY
        return Technique.FRAME_TO_FRAME_CHAIN

    # LUẬT 4 — fallback an toàn cuối cùng
    return Technique.FRAME_TO_FRAME_CHAIN
