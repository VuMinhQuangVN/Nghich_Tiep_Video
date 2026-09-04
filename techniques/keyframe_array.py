"""
techniques/keyframe_array.py
--------------------------------
Implement keyframe_array.md: sinh N ảnh keyframe song song (giới hạn
concurrency), rồi gọi 1 LẦN DUY NHẤT API video với mode="keyframes" để engine
tự nội suy chuyển động mượt giữa các keyframe theo đúng thứ tự.
"""
from __future__ import annotations

from core.prompt_composer import keyframe_image_prompt, keyframe_video_prompt
from engines.base_engine import BaseEngine, VideoStatus
from orchestrator.polling_worker import poll_until_done
from orchestrator.task_queue import run_bounded
from techniques.base import BaseTechnique, TechniqueContext, TechniqueResult
from utils.logger import get_logger

log = get_logger(__name__)


class KeyframeArray(BaseTechnique):
    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def run(self, ctx: TechniqueContext) -> TechniqueResult:
        ref = [ctx.character_sheet_url] if ctx.character_sheet_url else None

        # Bước 1: sinh ảnh keyframe cho MỌI scene CÙNG LÚC, giới hạn concurrency
        async def make_image(scene):
            prompt = keyframe_image_prompt(scene.description, ctx.style)
            image = await self._engine.generate_image(prompt=prompt, reference_images=ref)
            return image.url_or_path

        factories = [(lambda s=s: make_image(s)) for s in ctx.scenes]
        image_results = await run_bounded(factories, ctx.max_concurrent_image_requests)

        keyframe_urls: list[str] = []
        warnings: list[str] = []
        for scene, result in zip(ctx.scenes, image_results):
            if isinstance(result, Exception):
                warnings.append(f"Scene {scene.index}: lỗi sinh keyframe ({result}) — đã bỏ qua")
                continue
            keyframe_urls.append(result)

        if len(keyframe_urls) < 2:
            raise RuntimeError(
                "keyframe_array cần tối thiểu 2 keyframe hợp lệ để tạo chuyển động, "
                f"chỉ có {len(keyframe_urls)}"
            )

        # Bước 2: 1 request video duy nhất cho cả chuỗi keyframe
        total_duration = sum(s.duration_sec for s in ctx.scenes)
        video_prompt = keyframe_video_prompt(ctx.subject_name, mood=ctx.style)
        video_id = await self._engine.submit_video_task(
            prompt=video_prompt,
            images=keyframe_urls,
            mode="keyframes",
            num_frames=_duration_to_frames(total_duration),
        )

        results = await poll_until_done(self._engine, [video_id], ctx.poll_interval_sec)
        handle = results[video_id]
        if handle.status != VideoStatus.COMPLETED:
            raise RuntimeError(f"Video keyframe_array thất bại: {handle.error}")

        dest = ctx.output_dir / "keyframe_array_final.mp4"
        await self._engine.download_video(handle.result_url, str(dest))
        return TechniqueResult(final_video_path=dest, segment_video_paths=[dest], warnings=warnings)


def _duration_to_frames(duration_sec: float, frame_rate: int = 24) -> int:
    return max(1, round(duration_sec * frame_rate))
