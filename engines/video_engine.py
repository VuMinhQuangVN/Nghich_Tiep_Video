"""Provider-neutral video engine interface used by Agnes adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod

from models.video_job import VideoJob


class VideoEngine(ABC):
    @abstractmethod
    async def submit_video(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
    ) -> VideoJob:
        raise NotImplementedError

    @abstractmethod
    async def poll_video(self, job: VideoJob) -> VideoJob:
        raise NotImplementedError

    @abstractmethod
    async def download_video(self, job: VideoJob, dest_path: str) -> str:
        raise NotImplementedError
