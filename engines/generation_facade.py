"""
engines/generation_facade.py
-----------------------------
Facade bọc AgnesClient — expose các method mà pipeline cần,
thêm analyze_with_images() để CreativeDirector gọi AI với ảnh.
"""
from __future__ import annotations

from config import settings
from engines.agnes_client import AgnesClient
from engines.base_engine import ImageResult, VideoTaskHandle, VideoStatus
from utils.logger import get_logger

log = get_logger(__name__)


class GenerationFacade:
    """Wrapper đơn giản, dễ mock trong test."""

    def __init__(self, client: AgnesClient, video_engine=None):
        self._client = client
        self._video_engine = video_engine
        self._video_tasks: dict[str, str] = {}

    async def analyze_with_images(self, images: list[str], prompt: str) -> str:
        """Gọi vision model với nhiều ảnh — dùng ảnh đầu tiên, mention phần còn lại trong prompt."""
        if not images:
            raise ValueError("Cần ít nhất 1 ảnh để phân tích")

        # Agnes vision nhận 1 ảnh/lần — nếu nhiều ảnh, ghép chú thích vào prompt
        primary_image = images[0]
        extra_note = ""
        if len(images) > 1:
            extra_note = f"\n(Có {len(images)} ảnh sản phẩm, ảnh chính đính kèm, hãy suy luận từ ảnh này.)"

        return await self._client.analyze_image(
            image_path_or_url=primary_image,
            question=prompt + extra_note,
        )

    async def generate_image(
        self,
        prompt: str,
        ratio: str = "9:16",
        size: str = "2K",
        reference_images: list[str] | None = None,
    ) -> ImageResult:
        return await self._client.generate_image(
            prompt=prompt,
            ratio=ratio,
            size=size,
            reference_images=reference_images,
        )

    async def submit_video_task(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "img2video",
        aspect_ratio: str = "9:16",
        seconds: str | None = None,
        model: str | None = None,
    ) -> str:
        selected = self._video_engine
        selected_model = model or getattr(selected, "model_name", None) or settings.agnes_models.video
        fallback = getattr(selected, "fallback_model", None)

        # Video 2.5 Flash only accepts 4-12 seconds. If a caller requests an
        # unsupported duration, route the task to the stable V2.0 contract.
        if (
            fallback
            and selected_model.lower().strip() == "agnes-video-2.5-flash"
            and seconds is not None
        ):
            try:
                sec = float(seconds)
            except ValueError:
                sec = None
            if sec is not None and not 4 <= sec <= 12:
                selected_model = fallback
                log.info("Video duration %.1fs ngoài 4-12s: fallback sang %s", sec, selected_model)

        video_id = await self._client.submit_video_task(
            prompt=prompt,
            images=images,
            mode=mode,
            aspect_ratio=aspect_ratio,
            seconds=seconds if selected_model.lower().strip() == "agnes-video-2.5-flash" else None,
            model=selected_model,
        )
        self._video_tasks[video_id] = selected_model
        return video_id

    async def poll_video_task(
        self, video_id: str, model_name: str | None = None
    ) -> VideoTaskHandle:
        # Prefer the concrete model recorded at submit time. This is critical
        # when the submit path fell back from Video 2.5 Flash to V2.0.
        model = self._video_tasks.get(video_id) or model_name or settings.agnes_models.video
        handle = await self._client.poll_video_task(video_id, model_name=model)
        if handle.status in {VideoStatus.COMPLETED, VideoStatus.FAILED}:
            self._video_tasks.pop(video_id, None)
        return handle

    async def download_video(self, video_url: str, dest_path: str) -> str:
        return await self._client.download_video(video_url, dest_path)
