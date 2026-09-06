"""Fallback wrapper: experimental video first, stable V2.0 second."""
from __future__ import annotations

from engines.video_engine import VideoEngine
from models.video_job import VideoJob


class FallbackVideoEngine(VideoEngine):
    def __init__(self, primary: VideoEngine, fallback: VideoEngine):
        self.primary = primary
        self.fallback = fallback
        self._fallback_jobs: dict[str, VideoJob] = {}

    async def submit_video(self, *args, **kwargs) -> VideoJob:
        try:
            return await self.primary.submit_video(*args, **kwargs)
        except Exception:
            job = await self.fallback.submit_video(*args, **kwargs)
            self._fallback_jobs[job.job_id] = job
            return job

    async def poll_video(self, job: VideoJob) -> VideoJob:
        if job.job_id in self._fallback_jobs:
            return await self.fallback.poll_video(self._fallback_jobs[job.job_id])
        try:
            result = await self.primary.poll_video(job)
            if result.failed:
                fallback_job = await self.fallback.submit_video(
                    prompt=job.metadata["prompt"],
                    images=job.metadata.get("images"),
                    mode=job.metadata.get("mode", "ti2vid"),
                    num_frames=job.metadata.get("num_frames", 121),
                    frame_rate=job.metadata.get("frame_rate", 24),
                    negative_prompt=job.metadata.get("negative_prompt"),
                )
                self._fallback_jobs[fallback_job.job_id] = fallback_job
                return fallback_job
            return result
        except Exception:
            fallback_job = await self.fallback.submit_video(
                prompt=job.metadata["prompt"],
                images=job.metadata.get("images"),
                mode=job.metadata.get("mode", "ti2vid"),
                num_frames=job.metadata.get("num_frames", 121),
                frame_rate=job.metadata.get("frame_rate", 24),
                negative_prompt=job.metadata.get("negative_prompt"),
            )
            self._fallback_jobs[fallback_job.job_id] = fallback_job
            return fallback_job

    async def download_video(self, job: VideoJob, dest_path: str) -> str:
        if job.job_id in self._fallback_jobs:
            return await self.fallback.download_video(job, dest_path)
        return await self.primary.download_video(job, dest_path)
