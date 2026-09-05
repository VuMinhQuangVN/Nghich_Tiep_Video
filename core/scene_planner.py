"""Phase 5: Scene Planner 2.0.

Turns an approved CreativePlan + SubjectLock into structured CreativeScene
objects.  This layer decides *how to tell the approved creative story*; it
must not redefine product identity or consistency requirements.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from engines.base_engine import BaseEngine
from models.creative_plan import CreativePlan, CreativeScene
from models.subject_lock import SubjectLock
from utils.logger import get_logger

log = get_logger(__name__)


class ScenePlanner:
    """Phase 5 planner. One LLM call plans the complete scene list."""

    SYSTEM_PROMPT = """
Bạn là Scene Planner 2.0 của hệ thống AI tạo video quảng cáo sản phẩm.

Nhiệm vụ: biến CreativePlan đã được duyệt thành storyboard cấp SCENE.
Bạn quyết định cách kể câu chuyện qua các scene, nhưng KHÔNG được thay đổi
nhận diện sản phẩm hoặc các invariant trong SubjectLock.

QUY TẮC BẮT BUỘC:
1. Sản phẩm là chủ thể chính. Không tự phát minh đặc điểm, màu sắc, logo,
   hình dáng, chất liệu, công dụng hay claim mới cho sản phẩm.
2. Mọi scene phải phù hợp với concept, visual style, script, platform và
   duration đã được duyệt.
3. SubjectLock.invariants là các ràng buộc bất biến, phải được tôn trọng
   xuyên suốt toàn bộ scene.
4. Chỉ mô tả character/action của recurring character khi
   SubjectLock.character_required=true. Khi false, không tạo character action.
5. Không tạo SHOT. Đây chỉ là scene-level planning; camera ở đây là định hướng
   cấp scene, Shot Planner ở Phase 6 sẽ chi tiết hóa camera/shot.
6. Phân bổ duration hợp lý và tổng duration không vượt quá 25% duration yêu cầu.
7. Giữ voiceover/text overlay/CTA bám theo ScriptPlan; không tự thêm claim.
8. Trả về DUY NHẤT JSON array hợp lệ, không markdown, không giải thích.

SCHEMA MỖI SCENE:
{
  "index": 1,
  "objective": "mục tiêu của scene",
  "description": "mô tả visual cấp scene",
  "duration_sec": 4,
  "camera": "định hướng camera cấp scene",
  "camera_motion": "chuyển động camera",
  "framing": "cỡ khung hình",
  "product_visibility": "mức độ/ trạng thái xuất hiện của sản phẩm",
  "product_position": "vị trí tương đối của sản phẩm",
  "character_action": "hành động của recurring character hoặc chuỗi rỗng",
  "environment": "bối cảnh",
  "lighting": "ánh sáng",
  "mood": "cảm xúc",
  "transition": "chuyển cảnh",
  "voiceover": "voice-over của scene hoặc chuỗi rỗng",
  "text_overlay": "text overlay của scene hoặc chuỗi rỗng",
  "cta": "CTA của scene hoặc chuỗi rỗng"
}
""".strip()

    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def plan(
        self,
        creative_plan_or_script: CreativePlan | str,
        subject_lock: SubjectLock | None = None,
        style_hint: str = "",
    ) -> list[CreativeScene]:
        """Plan scenes using the Phase 5 contract, while preserving legacy callers.

        New code passes ``CreativePlan`` + ``SubjectLock``. Existing generation
        callers may still pass ``script_text`` + ``style_hint`` until Phase 10
        integrates the creative pipeline.
        """
        if isinstance(creative_plan_or_script, CreativePlan):
            if subject_lock is None:
                raise ValueError("ScenePlanner requires a SubjectLock for CreativePlan input")
            return await self.plan_creative(creative_plan_or_script, subject_lock)

        if isinstance(creative_plan_or_script, str):
            return await self.plan_legacy(creative_plan_or_script, style_hint)

        raise TypeError("ScenePlanner.plan requires CreativePlan or script text")

    async def plan_creative(
        self,
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
    ) -> list[CreativeScene]:
        """Create scenes from approved creative data and consistency contract."""
        self._validate_inputs(creative_plan, subject_lock)
        prompt = self._build_prompt(creative_plan, subject_lock)
        log.info("Đang lập scene plan 2.0...")

        raw = await self._engine.plan_scenes(prompt, "")
        scenes = self._parse_response(raw)
        scenes = self._normalize_and_validate_scenes(scenes, creative_plan, subject_lock)

        log.info(f"Đã lập {len(scenes)} scene")
        return scenes

    # Backward-compatible adapter for the old generation pipeline. Phase 10
    # can replace this with the CreativePlan/SubjectLock path.
    async def plan_legacy(self, script_text: str, style_hint: str = "") -> list[CreativeScene]:
        raw_scenes = await self._engine.plan_scenes(script_text, style_hint)
        return self._normalize_legacy(raw_scenes)

    @staticmethod
    def _validate_inputs(plan: CreativePlan, lock: SubjectLock) -> None:
        if not isinstance(plan, CreativePlan):
            raise TypeError("ScenePlanner requires a CreativePlan")
        if not isinstance(lock, SubjectLock):
            raise TypeError("ScenePlanner requires a SubjectLock")
        if not plan.input.product_reference_urls:
            raise ValueError("CreativePlan requires at least one product reference URL")
        if not plan.input.goal.strip():
            raise ValueError("CreativePlan.input.goal must not be empty")
        if not plan.input.platform.strip():
            raise ValueError("CreativePlan.input.platform must not be empty")
        if plan.input.duration_sec <= 0:
            raise ValueError("CreativePlan.input.duration_sec must be greater than 0")
        lock.validate()
        if lock.character_required and not plan.character.required:
            raise ValueError(
                "SubjectLock requires a character but CreativePlan.character.required is False"
            )
        if plan.character.required and not lock.character_required:
            raise ValueError(
                "CreativePlan requires a character but SubjectLock.character_required is False"
            )

    @classmethod
    def _build_prompt(cls, plan: CreativePlan, lock: SubjectLock) -> str:
        payload = {
            "creative_plan": {
                "input": asdict(plan.input),
                "product": asdict(plan.product),
                "audience": asdict(plan.audience),
                "concept": asdict(plan.concept),
                "visual_style": asdict(plan.visual_style),
                "character": asdict(plan.character),
                "script": asdict(plan.script),
            },
            "subject_lock": lock.to_dict(),
        }
        return f"{cls.SYSTEM_PROMPT}\n\nDỮ LIỆU ĐÃ ĐƯỢC DUYỆT:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

    @staticmethod
    def _parse_response(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            data = raw
        else:
            text = (raw or "").strip()
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                start, end = text.find("["), text.rfind("]")
                if start < 0 or end <= start:
                    raise ValueError("Scene Planner did not return valid JSON array")
                try:
                    data = json.loads(text[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise ValueError("Scene Planner did not return valid JSON array") from exc

        if not isinstance(data, list) or not data:
            raise ValueError("Scene Planner response must be a non-empty JSON array")
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("Every scene must be a JSON object")
        return data

    @classmethod
    def _normalize_and_validate_scenes(
        cls,
        raw_scenes: list[dict[str, Any]],
        plan: CreativePlan,
        lock: SubjectLock,
    ) -> list[CreativeScene]:
        scenes: list[CreativeScene] = []
        total = 0.0

        for position, item in enumerate(raw_scenes, start=1):
            index = cls._positive_int(item.get("index", position), position)
            if index != position:
                raise ValueError(
                    f"Scene indexes must be sequential starting from 1 (expected {position}, got {index})"
                )

            duration = cls._positive_float(item.get("duration_sec", 4), 4.0)
            scene = CreativeScene(
                index=index,
                objective=cls._text(item.get("objective")),
                description=cls._text(item.get("description")),
                duration_sec=duration,
                camera=cls._text(item.get("camera")),
                camera_motion=cls._text(item.get("camera_motion")),
                framing=cls._text(item.get("framing")),
                product_visibility=cls._text(item.get("product_visibility")),
                product_position=cls._text(item.get("product_position")),
                character_action=cls._text(item.get("character_action")),
                environment=cls._text(item.get("environment")),
                lighting=cls._text(item.get("lighting")),
                mood=cls._text(item.get("mood")),
                transition=cls._text(item.get("transition")),
                voiceover=cls._text(item.get("voiceover")),
                text_overlay=cls._text(item.get("text_overlay")),
                cta=cls._text(item.get("cta")),
            )

            if not scene.description:
                raise ValueError(f"Scene {index} description must not be empty")
            if not scene.objective:
                raise ValueError(f"Scene {index} objective must not be empty")
            if not scene.product_visibility:
                raise ValueError(f"Scene {index} product_visibility must not be empty")
            if not lock.character_required and scene.character_action:
                raise ValueError(
                    f"Scene {index} contains character_action but character lock is disabled"
                )

            total += duration
            scenes.append(scene)

        if total > plan.input.duration_sec * 1.25:
            raise ValueError(
                "Total scene duration is more than 25% above requested video duration"
            )
        return scenes

    @staticmethod
    def _normalize_legacy(raw_scenes: list[dict[str, Any]]) -> list[CreativeScene]:
        result = []
        for i, item in enumerate(raw_scenes, start=1):
            result.append(
                CreativeScene(
                    index=i,
                    description=str(item.get("description", "")).strip(),
                    duration_sec=float(item.get("duration_sec", 4)),
                    camera_motion=str(item.get("camera_move", "")).strip(),
                )
            )
        return result

    @staticmethod
    def _text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _positive_float(value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        if number <= 0:
            raise ValueError("Scene duration_sec must be greater than 0")
        return number

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if number <= 0:
            raise ValueError("Scene index must be greater than 0")
        return number
