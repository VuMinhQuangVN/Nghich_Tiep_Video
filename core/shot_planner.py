"""Phase 6: Shot Planner.

Expands one approved scene into concrete camera shots. This layer does not
rewrite the creative concept or product/character identity and does not create
the final consistency-heavy engine prompt; that belongs to Phase 7.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from engines.base_engine import BaseEngine
from models.creative_plan import CreativePlan, CreativeScene
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock
from utils.logger import get_logger

log = get_logger(__name__)


class ShotPlanner:
    """Turn a scene into a sequence of concrete shots using one LLM call."""

    SYSTEM_PROMPT = """
Bạn là Shot Planner của hệ thống AI tạo video quảng cáo sản phẩm.

Nhiệm vụ: biến MỘT scene đã được duyệt thành danh sách SHOT cụ thể. Scene là
cấp độ kể chuyện; shot là cấp độ quay thực tế. Bạn chỉ chi tiết hóa cách quay,
không được viết lại concept hoặc thay đổi nhận diện sản phẩm/character.

QUY TẮC BẮT BUỘC:
1. Mọi shot phải phục vụ objective và description của scene.
2. Không phát minh đặc điểm, màu sắc, logo, packaging, chất liệu, công dụng
   hoặc claim mới cho sản phẩm.
3. Tôn trọng toàn bộ SubjectLock.invariants.
4. Nếu character_required=false thì không tạo shot có character action.
5. Không tạo scene mới và không gộp nhiều scene vào một shot plan.
6. Tổng duration của các shot phải xấp xỉ duration của scene và KHÔNG vượt
   quá 25% duration của scene.
7. Shot phải thể hiện rõ camera thực sự quay như thế nào: shot_type,
   framing, camera_angle, camera_motion, subject_position.
8. generation_prompt chỉ là DRAFT ở cấp shot. Không cố tạo prompt consistency
   cuối cùng; Phase 7 sẽ làm việc đó.
9. Không thêm voiceover, text overlay hoặc CTA mới; các nội dung đó thuộc scene.
10. Trả về DUY NHẤT JSON array hợp lệ, không markdown, không giải thích.

SCHEMA MỖI SHOT:
{
  "index": 1,
  "shot_type": "macro product shot",
  "framing": "extreme close-up",
  "camera_angle": "eye level",
  "camera_motion": "slow push-in",
  "subject_position": "center frame",
  "action": "product remains still",
  "environment": "clean studio",
  "lighting": "soft studio light",
  "duration_sec": 2,
  "generation_prompt": "draft visual prompt for this shot"
}
""".strip()

    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def plan_scene(
        self,
        scene: CreativeScene,
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
    ) -> list[CreativeShot]:
        self._validate_inputs(scene, creative_plan, subject_lock)
        prompt = self._build_prompt(scene, creative_plan, subject_lock)
        log.info("Đang lập shot plan cho scene %s...", scene.index)

        # Keep Phase 6 sequential: one LLM call for one scene.
        raw = await self._engine.plan_scenes(prompt, "")
        shots = self._parse_response(raw)
        result = self._normalize_and_validate(shots, scene, subject_lock)

        log.info("Scene %s có %s shot", scene.index, len(result))
        return result

    async def plan(
        self,
        scenes: list[CreativeScene],
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
    ) -> dict[int, list[CreativeShot]]:
        """Plan every scene sequentially and return shots grouped by scene index."""
        self._validate_plan_inputs(scenes, creative_plan, subject_lock)
        planned: dict[int, list[CreativeShot]] = {}
        for scene in scenes:
            planned[scene.index] = await self.plan_scene(scene, creative_plan, subject_lock)
        return planned

    @staticmethod
    def _validate_plan_inputs(
        scenes: list[CreativeScene],
        plan: CreativePlan,
        lock: SubjectLock,
    ) -> None:
        if not isinstance(scenes, list) or not scenes:
            raise ValueError("ShotPlanner requires a non-empty scene list")
        expected = 1
        for scene in scenes:
            if not isinstance(scene, CreativeScene):
                raise TypeError("Every item in scenes must be a CreativeScene")
            if scene.index != expected:
                raise ValueError(
                    f"Scene indexes must be sequential starting from 1 (expected {expected}, got {scene.index})"
                )
            expected += 1
        ShotPlanner._validate_inputs(scenes[0], plan, lock, validate_scene_only=False)

    @staticmethod
    def _validate_inputs(
        scene: CreativeScene,
        plan: CreativePlan,
        lock: SubjectLock,
        validate_scene_only: bool = True,
    ) -> None:
        if not isinstance(scene, CreativeScene):
            raise TypeError("ShotPlanner requires a CreativeScene")
        if not isinstance(plan, CreativePlan):
            raise TypeError("ShotPlanner requires a CreativePlan")
        if not isinstance(lock, SubjectLock):
            raise TypeError("ShotPlanner requires a SubjectLock")
        if scene.index <= 0 or scene.duration_sec <= 0:
            raise ValueError("Scene index and duration_sec must be greater than 0")
        if not scene.description.strip():
            raise ValueError(f"Scene {scene.index} description must not be empty")
        if not scene.objective.strip():
            raise ValueError(f"Scene {scene.index} objective must not be empty")
        if not scene.product_visibility.strip():
            raise ValueError(f"Scene {scene.index} product_visibility must not be empty")
        if plan.character.required != lock.character_required:
            raise ValueError("CreativePlan and SubjectLock character state must match")
        if not lock.character_required and scene.character_action.strip():
            raise ValueError(
                f"Scene {scene.index} contains character_action but character lock is disabled"
            )
        lock.validate()

    @classmethod
    def _build_prompt(
        cls,
        scene: CreativeScene,
        plan: CreativePlan,
        lock: SubjectLock,
    ) -> str:
        payload = {
            "scene": asdict(scene),
            "creative_context": {
                "goal": plan.input.goal,
                "platform": plan.input.platform,
                "duration_sec": plan.input.duration_sec,
                "product": asdict(plan.product),
                "visual_style": asdict(plan.visual_style),
                "character": asdict(plan.character),
            },
            "subject_lock": lock.to_dict(),
        }
        return (
            f"{cls.SYSTEM_PROMPT}\n\nDỮ LIỆU SCENE ĐÃ ĐƯỢC DUYỆT:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

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
                    raise ValueError("Shot Planner did not return valid JSON array")
                try:
                    data = json.loads(text[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise ValueError("Shot Planner did not return valid JSON array") from exc

        if not isinstance(data, list) or not data:
            raise ValueError("Shot Planner response must be a non-empty JSON array")
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("Every shot must be a JSON object")
        return data

    @classmethod
    def _normalize_and_validate(
        cls,
        raw_shots: list[dict[str, Any]],
        scene: CreativeScene,
        lock: SubjectLock,
    ) -> list[CreativeShot]:
        result: list[CreativeShot] = []
        total = 0.0

        for position, item in enumerate(raw_shots, start=1):
            index = cls._positive_int(item.get("index", position), position)
            if index != position:
                raise ValueError(
                    f"Shot indexes must be sequential starting from 1 (expected {position}, got {index})"
                )

            action = cls._text(item.get("action"))
            if not lock.character_required and cls._mentions_character(action):
                raise ValueError(
                    f"Shot {index} contains character action but character lock is disabled"
                )

            shot = CreativeShot(
                index=index,
                shot_type=cls._text(item.get("shot_type")),
                framing=cls._text(item.get("framing")),
                camera_angle=cls._text(item.get("camera_angle")),
                camera_motion=cls._text(item.get("camera_motion")),
                subject_position=cls._text(item.get("subject_position")),
                action=action,
                environment=cls._text(item.get("environment")),
                lighting=cls._text(item.get("lighting")),
                duration_sec=cls._positive_float(item.get("duration_sec", 1), 1.0),
                generation_prompt=cls._text(item.get("generation_prompt")),
            )

            for field_name in ("shot_type", "framing", "camera_angle", "camera_motion", "subject_position"):
                if not getattr(shot, field_name):
                    raise ValueError(f"Shot {index} {field_name} must not be empty")
            if not shot.generation_prompt:
                raise ValueError(f"Shot {index} generation_prompt must not be empty")

            total += shot.duration_sec
            result.append(shot)

        if total > scene.duration_sec * 1.25:
            raise ValueError(
                f"Total shot duration for scene {scene.index} is more than 25% above scene duration"
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
            raise ValueError("Shot duration_sec must be greater than 0")
        return number

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if number <= 0:
            raise ValueError("Shot index must be greater than 0")
        return number

    @staticmethod
    def _mentions_character(action: str) -> bool:
        if not action:
            return False
        text = action.lower()
        markers = (
            "character", "person", "woman", "man", "model", "girl", "boy",
            "nhân vật", "người mẫu", "cô gái", "chàng trai", "người phụ nữ", "người đàn ông",
        )
        return any(marker in text for marker in markers)
