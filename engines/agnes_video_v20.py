"""Agnes Video V2.0 stable adapter."""
from __future__ import annotations

from engines.agnes_client import AgnesClient
from engines.video_engine import VideoEngine
from models.video_job import VideoJob, VideoJobStatus


class AgnesVideoV20Adapter(VideoEngine):
    def __init__(self, client: AgnesClient):
        self.client = client

    @property
    def model(self) -> str:
        from config import settings
        return settings.agnes_models.video

    async def submit_video(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
    ) -> VideoJob:
        video_id = await self.client.submit_video_task(
            prompt=prompt,
            images=images,
            mode=mode,
            num_frames=num_frames,
            frame_rate=frame_rate,
            negative_prompt=negative_prompt,
            model=self.model,
        )
        return VideoJob(job_id=video_id, model=self.model, metadata={"prompt": prompt, "images": images, "mode": mode, "num_frames": num_frames, "frame_rate": frame_rate, "negative_prompt": negative_prompt})

    async def poll_video(self, job: VideoJob) -> VideoJob:
        handle = await self.client.poll_video_task(job.job_id, model_name=self.model)
        return VideoJob(
            job_id=job.job_id,
            model=self.model,
            status=VideoJobStatus(handle.status.value),
            result_url=handle.result_url,
            error=handle.error,
            metadata={**job.metadata, **handle.metadata},
        )

    async def download_video(self, job: VideoJob, dest_path: str) -> str:
        if not job.result_url:
            raise ValueError("VideoJob chưa có result_url để download")
        return await self.client.download_video(job.result_url, dest_path)
