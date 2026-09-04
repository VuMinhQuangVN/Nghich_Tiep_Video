"""
core/scene_planner.py
-----------------------
Gọi engine.plan_scenes() (agnes-2.5-flash) 1 LẦN DUY NHẤT để chia toàn bộ
kịch bản thành scene[] có cấu trúc (đúng thiết kế mục 3 trong
software-design.md: Bước 2 là tuần tự, không cần song song).
"""
from __future__ import annotations

from dataclasses import dataclass

from engines.base_engine import BaseEngine
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Scene:
    index: int
    description: str
    duration_sec: float
    camera_move: str = ""


class ScenePlanner:
    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def plan(self, script_text: str, style_hint: str = "") -> list[Scene]:
        log.info("Đang chia kịch bản thành scene...")
        raw_scenes = await self._engine.plan_scenes(script_text, style_hint)
        scenes = [
            Scene(
                index=s.get("index", i + 1),
                description=s.get("description", ""),
                duration_sec=float(s.get("duration_sec", 4)),
                camera_move=s.get("camera_move", ""),
            )
            for i, s in enumerate(raw_scenes)
        ]
        log.info(f"Đã chia thành {len(scenes)} scene")
        return scenes
