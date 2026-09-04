"""
techniques/base.py
---------------------
Strategy Pattern: mỗi technique (single_shot_direct, frame_to_frame_chain,
keyframe_array, ...) implement cùng 1 interface `run()`. router.py chỉ chọn
TÊN technique; pipeline_runner.py map tên -> instance rồi gọi `.run()` mà
không cần biết chi tiết bên trong -> Open/Closed Principle (thêm technique
mới không cần sửa pipeline_runner).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from core.scene_planner import Scene


@dataclass
class TechniqueContext:
    scenes: list[Scene]
    style: str
    subject_name: str
    character_sheet_url: str | None
    output_dir: Path
    max_concurrent_image_requests: int
    max_concurrent_video_submit: int
    poll_interval_sec: float


@dataclass
class TechniqueResult:
    final_video_path: Path
    segment_video_paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BaseTechnique(ABC):
    @abstractmethod
    async def run(self, ctx: TechniqueContext) -> TechniqueResult:
        raise NotImplementedError
