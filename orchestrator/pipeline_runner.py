"""
orchestrator/pipeline_runner.py
--------------------------------
Pipeline chính: nhận PipelineInput → loop từng shot:
  1. Gen ảnh storyboard (với reference sản phẩm)
  2. Submit video task (img2video từ ảnh storyboard)
  3. Poll cho đến khi xong
  4. Download video
  5. Ghép tất cả cảnh lại

Học từ Flow app: đơn giản, tuần tự, không over-engineer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from engines.base_engine import VideoStatus
from engines.generation_facade import GenerationFacade
from models.creative_plan import CreativePlan, ShotPlan
from core.subject_lock import SubjectLock
from utils.ffmpeg_utils import concat_videos, trim_video
from utils.logger import get_logger
from config import settings

log = get_logger(__name__)


@dataclass
class PipelineInput:
    """Input cho PipelineRunner khi dùng theo kịch bản thủ công."""
    script_text: str
    style_hint: str
    subject_name: str
    reference_image_url: str | None
    keep_character_consistent: bool
    output_dir: Path
    max_concurrent_image_requests: int = 1
    max_concurrent_video_submit: int = 1
    poll_interval_sec: float = 4.0


@dataclass
class PipelineResult:
    final_video_path: Path
    warnings: list[str] = field(default_factory=list)


class PipelineRunner:
    """Chạy pipeline gen ảnh → gen video → ghép cho 1 CreativePlan."""

    def __init__(self, engine: GenerationFacade):
        self._engine = engine

    async def run(self, pipeline_input) -> PipelineResult:
        """Entry point — nhận PipelineInput hoặc CreativePlanInput."""
        if isinstance(pipeline_input, CreativePlanInput):
            return await self._run_creative(pipeline_input)
        raise TypeError(f"Không hỗ trợ loại pipeline input: {type(pipeline_input)}")

    async def _run_creative(self, inp: "CreativePlanInput") -> PipelineResult:
        plan = inp.creative_plan
        subject_lock = inp.subject_lock
        output_dir = inp.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        video_paths: list[Path] = []

        # IMPORTANT: shot.duration is the editorial timeline. Provider generation
        # duration may be 4s+ and is intentionally NOT the final timeline.
        log.info(
            "Editorial timeline: %.3fs / %d cảnh",
            sum(s.duration for s in plan.shots), len(plan.shots),
        )

        for i, shot in enumerate(plan.shots):
            log.info("Shot %d/%d: %s", i + 1, len(plan.shots), shot.description[:60])

            try:
                # Bước 1: Gen ảnh storyboard
                storyboard_path = await self._gen_storyboard(
                    shot=shot,
                    plan=plan,
                    subject_lock=subject_lock,
                    output_dir=output_dir,
                    shot_idx=i,
                )

                # Bước 2 & 3: Submit + poll video
                video_path = await self._gen_video(
                    shot=shot,
                    plan=plan,
                    storyboard_path=storyboard_path,
                    output_dir=output_dir,
                    shot_idx=i,
                    poll_interval=inp.poll_interval_sec,
                )

                # The AI clip can be longer than the shot in the script.
                # Trim BEFORE concat so final duration follows the script.
                trimmed_path = output_dir / f"shot_{i + 1:02d}_trimmed.mp4"
                await trim_video(video_path, trimmed_path, shot.duration)
                video_paths.append(trimmed_path)

            except Exception as e:
                msg = f"Shot {i + 1} thất bại: {e}"
                log.warning(msg)
                warnings.append(msg)

        if not video_paths:
            raise RuntimeError("Không có cảnh nào gen thành công")

        # Bước 4: Ghép tất cả
        log.info("Ghép %d cảnh thành video cuối...", len(video_paths))
        final_path = output_dir / "final_video.mp4"
        await concat_videos(video_paths, final_path)
        log.info("Hoàn tất: %s", final_path)

        return PipelineResult(final_video_path=final_path, warnings=warnings)

    async def _gen_storyboard(
        self,
        shot: ShotPlan,
        plan: CreativePlan,
        subject_lock: SubjectLock,
        output_dir: Path,
        shot_idx: int,
    ) -> str:
        """Gen ảnh keyframe cho shot. Trả về URL ảnh."""
        log.info("  → Gen storyboard ảnh...")

        style = plan.style_suggestion
        full_prompt = (
            f"{shot.common_visual_context}. "
            f"{shot.visual_prompt}. "
            f"Style: {style}, high-end cinematic commercial, "
            f"aspect ratio {plan.aspect_ratio}, 8k resolution, highly detailed."
        )

        result = await self._engine.generate_image(
            prompt=full_prompt,
            ratio=plan.aspect_ratio,
            size="2K",
            reference_images=subject_lock.reference_urls or None,
        )
        log.info("  → Storyboard OK: %s", result.url_or_path[:80])
        return result.url_or_path

    async def _gen_video(
        self,
        shot: ShotPlan,
        plan: CreativePlan,
        storyboard_path: str,
        output_dir: Path,
        shot_idx: int,
        poll_interval: float,
    ) -> Path:
        """Submit video task, poll đến khi done, download."""
        log.info("  → Submit video task (%.0fs)...", shot.duration)

        video_prompt = f"{shot.description}, smooth cinematic motion"
        # Agnes Video 2.5 Flash accepts generation lengths 4-12s.
        # Editorial duration may be 2-4s; generate 4s then trim deterministically.
        gen_seconds = max(4.0, min(12.0, float(shot.duration)))
        seconds = str(int(gen_seconds)) if gen_seconds.is_integer() else str(gen_seconds)

        video_id = await self._engine.submit_video_task(
            prompt=video_prompt,
            images=[storyboard_path],
            mode="reference",
            aspect_ratio=plan.aspect_ratio,
            seconds=seconds,
        )
        log.info("  → Video task %s submitted, đang poll...", video_id)

        # Poll đến khi xong
        handle = await self._poll_until_done(video_id, poll_interval)

        if not handle.result_url:
            raise RuntimeError(f"Video task {video_id} hoàn tất nhưng không có URL")

        # Download
        dest = output_dir / f"shot_{shot_idx + 1:02d}.mp4"
        await self._engine.download_video(handle.result_url, str(dest))
        log.info("  → Download xong: %s", dest)
        return dest

    async def _poll_until_done(
        self, video_id: str, interval: float, model_name: str | None = None
    ):
        """Poll video_id cho đến khi COMPLETED hoặc FAILED."""
        max_wait = 600  # 10 phút tối đa
        elapsed = 0.0
        current_interval = interval

        while elapsed < max_wait:
            await asyncio.sleep(current_interval)
            elapsed += current_interval

            handle = await self._engine.poll_video_task(video_id, model_name=model_name)
            log.info("  → Poll %s: %s (%.0fs elapsed)", video_id, handle.status, elapsed)

            if handle.status == VideoStatus.COMPLETED:
                return handle
            if handle.status == VideoStatus.FAILED:
                raise RuntimeError(f"Video task {video_id} thất bại: {handle.error}")

            # Backoff nhẹ nếu chờ lâu
            if elapsed > 60:
                current_interval = min(settings.poll_max_backoff_sec, current_interval * 1.5)

        raise TimeoutError(f"Video task {video_id} timeout sau {max_wait}s")


@dataclass
class CreativePlanInput:
    """Input cho PipelineRunner khi dùng CreativePlan."""
    creative_plan: CreativePlan
    subject_lock: SubjectLock
    output_dir: Path
    max_concurrent_image_requests: int = 1
    max_concurrent_video_submit: int = 1
    poll_interval_sec: float = 4.0
