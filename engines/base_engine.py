"""
engines/base_engine.py
------------------------
Interface chung mọi engine tạo ảnh/video phải implement (VD: agnes_client.py
hiện tại, sau này omni_flash_client.py). Phần còn lại của hệ thống
(techniques, orchestrator) chỉ phụ thuộc vào interface này, KHÔNG phụ thuộc
trực tiếp vào AgnesClient -> Dependency Inversion Principle, dễ thêm engine
mới mà không sửa code cũ (Open/Closed Principle).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class VideoStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


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


@dataclass
class EngineCapabilities:
    supports_storyboard_read: bool = False
    supports_keyframe_array: bool = False
    supports_edit: bool = False
    supports_image_to_video: bool = True
    supports_text_to_video: bool = True
    max_clip_duration_sec: float = 10
    min_clip_duration_sec: float = 1


class BaseEngine(ABC):
    """Mọi engine cụ thể phải implement đủ các method dưới đây."""

    capabilities: EngineCapabilities

    @abstractmethod
    async def analyze_image(self, image_path_or_url: str, question: str) -> str:
        """Vision understanding: hỏi LLM về nội dung 1 ảnh, trả về text mô tả."""
        raise NotImplementedError

    @abstractmethod
    async def plan_scenes(self, script_text: str, style_hint: str = "") -> list[dict]:
        """Dùng LLM chia kịch bản thành danh sách scene có cấu trúc."""
        raise NotImplementedError

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        ratio: str = "9:16",
        size: str = "2K",
        reference_images: list[str] | None = None,
    ) -> ImageResult:
        raise NotImplementedError

    @abstractmethod
    async def submit_video_task(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
    ) -> str:
        """Submit task tạo video (async), trả về video_id."""
        raise NotImplementedError

    @abstractmethod
    async def poll_video_task(self, video_id: str) -> VideoTaskHandle:
        raise NotImplementedError

    @abstractmethod
    async def download_video(self, video_url: str, dest_path: str) -> str:
        raise NotImplementedError
