"""
techniques/frame_to_frame_chain.py
--------------------------------------
Implement frame_to_frame_chain.md: fallback an toàn cho mọi engine.
BẮT BUỘC TUẦN TỰ giữa các scene (scene N cần frame cuối của scene N-1 làm
input) — đây là kỹ thuật duy nhất KHÔNG song song hoá được ở bước video,
nhưng trích frame (ffmpeg) + polling vẫn chạy nền không chặn luồng chính.
"""
from __future__ import annotations

from core.prompt_composer import scene_image_prompt, scene_video_prompt
from engines.base_engine import BaseEngine, VideoStatus
from orchestrator.polling_worker import poll_until_done
from techniques.base import BaseTechnique, TechniqueContext, TechniqueResult
from utils.ffmpeg_utils import concat_videos, extract_last_frame
from utils.logger import get_logger

log = get_logger(__name__)


class FrameToFrameChain(BaseTechnique):
    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def run(self, ctx: TechniqueContext) -> TechniqueResult:
        segment_paths: list = []
        warnings: list[str] = []
        anchor_image = ctx.character_sheet_url  # None nếu không có nhân vật lặp lại

        # Re-anchor mỗi 3 scene để giảm "trôi" style, theo khuyến nghị trong doc.
        original_anchor = ctx.character_sheet_url

        for i, scene in enumerate(ctx.scenes, start=1):
            if anchor_image is None:
                img_prompt = scene_image_prompt(scene.description, ctx.style)
                image = await self._engine.generate_image(prompt=img_prompt)
                anchor_image = image.url_or_path

            video_prompt = scene_video_prompt(
                scene.description, scene.camera_move, ctx.style, scene.duration_sec
            )
            video_id = await self._engine.submit_video_task(
                prompt=video_prompt,
                images=[anchor_image],
                mode="ti2vid",
                num_frames=_duration_to_frames(scene.duration_sec),
            )

            results = await poll_until_done(self._engine, [video_id], ctx.poll_interval_sec)
            handle = results[video_id]
            if handle.status != VideoStatus.COMPLETED:
                warnings.append(f"Scene {scene.index}: lỗi ({handle.error}) — đã bỏ qua scene này")
                continue

            seg_path = ctx.output_dir / f"scene_{scene.index}.mp4"
            await self._engine.download_video(handle.result_url, str(seg_path))
            segment_paths.append(seg_path)

            # Trích frame cuối làm anchor cho scene kế tiếp
            frame_path = ctx.output_dir / f"scene_{scene.index}_last_frame.png"
            await extract_last_frame(seg_path, frame_path)
            anchor_image = str(frame_path)

            # Re-anchor về character sheet gốc mỗi 3 scene để giảm drift
            if original_anchor and i % 3 == 0:
                anchor_image = original_anchor

        if not segment_paths:
            raise RuntimeError("Tất cả scene đều thất bại, không có video nào để ghép")

        final_path = ctx.output_dir / "frame_to_frame_final.mp4"
        await concat_videos(segment_paths, final_path)
        return TechniqueResult(
            final_video_path=final_path, segment_video_paths=segment_paths, warnings=warnings
        )


def _duration_to_frames(duration_sec: float, frame_rate: int = 24) -> int:
    return max(1, round(duration_sec * frame_rate))
