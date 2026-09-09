"""
engines/base_engine.py
-----------------------
Interface cơ bản cho mọi generation engine.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class VideoStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EngineCapabilities:
    # Legacy capability retained only for config compatibility; request-mode
    # selection is no longer part of the Creative Brain → Pipeline flow.
    supports_keyframe_array: bool = False
    supports_storyboard_read: bool = False
    supports_edit: bool = False
    supports_image_to_video: bool = True
    supports_text_to_video: bool = True
    max_clip_duration_sec: float = 18
    min_clip_duration_sec: float = 1


@dataclass
class ImageResult:
    url_or_path: str
    is_local_path: bool = False


@dataclass
class VideoTaskHandle:
    video_id: str
    status: VideoStatus = VideoStatus.QUEUED
    result_url: str | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class BaseEngine(ABC):
    capabilities: EngineCapabilities

    async def analyze_image(self, image_path_or_url: str, question: str) -> str:
        raise NotImplementedError

    async def generate_image(
        self,
        prompt: str,
        ratio: str = "9:16",
        size: str = "2K",
        reference_images: list[str] | None = None,
    ) -> ImageResult:
        raise NotImplementedError

    async def submit_video_task(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
        *,
        model: str | None = None,
        size: str | None = None,
        seconds: str | None = None,
        n: int | None = None,
        aspect_ratio: str = "9:16",
    ) -> str:
        raise NotImplementedError

    async def poll_video_task(self, video_id: str, *, model_name: str | None = None) -> VideoTaskHandle:
        raise NotImplementedError

    async def download_video(self, video_url: str, dest_path: str) -> str:
        raise NotImplementedError
