"""
techniques/single_shot_direct.py
------------------------------------
1 ảnh -> 1 video. Dùng khi scene_count == 1 (single_shot_direct.md).
"""
from __future__ import annotations

from pathlib import Path


from engines.base_engine import BaseEngine, VideoStatus
from orchestrator.polling_worker import poll_until_done
from techniques.base import BaseTechnique, TechniqueContext, TechniqueResult
from utils.logger import get_logger

log = get_logger(__name__)


class SingleShotDirect(BaseTechnique):
    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def run(self, ctx: TechniqueContext) -> TechniqueResult:
        scene = ctx.scenes[0]
        ref = BaseTechnique.product_reference_images(ctx)
        img_prompt = BaseTechnique.combined_prompt_for_scene(ctx, scene)
        ratio, resolution = BaseTechnique.image_generation_settings(ctx)
        image = await self._engine.generate_image(prompt=img_prompt, ratio=ratio, size=resolution, reference_images=ref or None)
        source_image = image.url_or_path

        video_prompt = BaseTechnique.combined_prompt_for_scene(ctx, scene)
        video_prompt += (
            f"\n\nCamera motion: {scene.camera_motion}. "
            f"Style: {ctx.style}. Duration: {scene.duration_sec:g}s."
        )
        video_id = await self._engine.submit_video_task(
            prompt=video_prompt,
            images=[source_image],
            mode="ti2vid",
            num_frames=_duration_to_frames(scene.duration_sec),
        )

        results = await poll_until_done(self._engine, [video_id], ctx.poll_interval_sec)
        handle = results[video_id]
        if handle.status != VideoStatus.COMPLETED:
            raise RuntimeError(f"Video scene duy nhất thất bại: {handle.error}")

        dest = ctx.output_dir / "scene_1.mp4"
        await self._engine.download_video(handle.result_url, str(dest))
        return TechniqueResult(final_video_path=dest, segment_video_paths=[dest])


def _duration_to_frames(duration_sec: float, frame_rate: int = 24) -> int:
    return max(1, round(duration_sec * frame_rate))
