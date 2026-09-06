"""Agnes Video 2.5 Flash experimental adapter.

The experimental API is intentionally isolated from the stable V2.0 adapter.
It uses 720P, one output, 4-12 seconds, and at most five reference images.
"""
from __future__ import annotations

from engines.agnes_client import AgnesClient
from engines.video_engine import VideoEngine
from models.video_job import VideoJob, VideoJobStatus


class AgnesVideo25FlashAdapter(VideoEngine):
    MAX_REFERENCE_IMAGES = 5
    MIN_SECONDS = 4
    MAX_SECONDS = 12

    def __init__(self, client: AgnesClient):
        self.client = client

    @property
    def model(self) -> str:
        from config import settings
        return settings.agnes_models.video_experimental

    @staticmethod
    def _seconds(num_frames: int, frame_rate: int) -> int:
        if frame_rate <= 0:
            raise ValueError("frame_rate must be greater than 0")
        return round(num_frames / frame_rate)

    async def submit_video(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
    ) -> VideoJob:
        references = list(images or [])
        if len(references) > self.MAX_REFERENCE_IMAGES:
            raise ValueError("Agnes Video 2.5 Flash supports at most 5 reference images")

        seconds = self._seconds(num_frames, frame_rate)
        if not self.MIN_SECONDS <= seconds <= self.MAX_SECONDS:
            raise ValueError("Agnes Video 2.5 Flash requires 4-12 seconds")

        if negative_prompt:
            prompt = f"{prompt}\n\nNegative prompt: {negative_prompt}"

        api_mode = "reference" if references else "text"
        video_id = await self.client.submit_video_task(
            prompt=prompt,
            images=references or None,
            mode=api_mode,
            num_frames=num_frames,
            frame_rate=frame_rate,
            model=self.model,
            size="720P",
            seconds=str(seconds),
            n=1,
        )
        return VideoJob(job_id=video_id, model=self.model, metadata={"prompt": prompt, "images": references, "mode": api_mode, "num_frames": num_frames, "frame_rate": frame_rate, "negative_prompt": negative_prompt, "seconds": seconds, "size": "720P"})

    async def poll_video(self, job: VideoJob) -> VideoJob:
        handle = await self.client.poll_video_task(job.job_id, model_name=self.model)
        return VideoJob(
            job_id=job.job_id,
            model=self.model,
            status=VideoJobStatus(handle.status.value),
            result_url=handle.result_url,
            error=handle.error,
            metadata=dict(job.metadata),
        )

    async def download_video(self, job: VideoJob, dest_path: str) -> str:
        if not job.result_url:
            raise ValueError("VideoJob chưa có result_url để download")
        return await self.client.download_video(job.result_url, dest_path)
