"""
orchestrator/creative_pipeline_adapter.py
------------------------------------------
Chuyển CreativePlan → CreativePlanInput để PipelineRunner chạy.
"""
from __future__ import annotations

from pathlib import Path

from core.subject_lock import SubjectLock
from models.creative_plan import CreativePlan
from orchestrator.pipeline_runner import CreativePlanInput
from utils.video_post_processor import PostProcessOptions


class CreativePipelineAdapter:
    @staticmethod
    def to_pipeline_input(
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
        output_dir: Path,
        max_concurrent_image_requests: int = 1,
        max_concurrent_video_submit: int = 1,
        poll_interval_sec: float = 4.0,
    ) -> CreativePlanInput:
        return CreativePlanInput(
            creative_plan=creative_plan,
            subject_lock=subject_lock,
            output_dir=output_dir,
            max_concurrent_image_requests=max_concurrent_image_requests,
            max_concurrent_video_submit=max_concurrent_video_submit,
            poll_interval_sec=poll_interval_sec,
        )

    @staticmethod
    def to_post_process_options(
        creative_plan: CreativePlan,
        voiceover_path: Path | None = None,
        background_music_path: Path | None = None,
        subtitles_path: Path | None = None,
    ) -> PostProcessOptions:
        return PostProcessOptions(
            target_ratio=creative_plan.aspect_ratio,
            target_duration_sec=creative_plan.total_duration,
            voiceover_path=voiceover_path,
            background_music_path=background_music_path,
            subtitles_path=subtitles_path,
        )
