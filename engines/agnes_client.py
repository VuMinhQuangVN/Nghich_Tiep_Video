"""
engines/agnes_client.py
-------------------------
Implement BaseEngine cho Agnes AI, dựa đúng theo knowledge-base/engines/agnes_ai.md:

- agnes-2.5-flash          -> /v1/chat/completions   (text + vision)
- agnes-image-2.1-flash    -> /v1/images/generations (text-to-image / image-to-image)
- agnes-video-v2.0         -> /v1/videos (submit, async) + GET /agnesapi?video_id=...(poll)

Điểm quan trọng đã theo đúng docs:
- response_format & mode/image nằm trong extra_body, KHÔNG ở top-level.
- num_frames phải theo luật 8n+1, tối đa 441.
- Có key rotation + retry với tenacity khi gặp 429/503.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from engines.base_engine import (
    BaseEngine,
    EngineCapabilities,
    ImageResult,
    VideoStatus,
    VideoTaskHandle,
)
from utils.key_rotation import KeyRotator
from utils.logger import get_logger

log = get_logger(__name__)


class RateLimitError(Exception):
    pass


class AgnesAPIError(Exception):
    pass


def nearest_valid_num_frames(target: int) -> int:
    """Ép num_frames về đúng luật 8n+1 (n nguyên), giới hạn [1, 441]."""
    target = max(1, min(441, target))
    n = round((target - 1) / 8)
    value = 8 * n + 1
    return max(1, min(441, value))


class AgnesClient(BaseEngine):
    capabilities = EngineCapabilities(
        supports_storyboard_read=False,
        supports_keyframe_array=True,
        supports_edit=False,
        supports_image_to_video=True,
        supports_text_to_video=True,
        max_clip_duration_sec=18,   # 441 frames / 24fps
        min_clip_duration_sec=1,
    )

    CHAT_MODEL = "agnes-2.5-flash"
    IMAGE_MODEL = "agnes-image-2.1-flash"
    VIDEO_MODEL = "agnes-video-v2.0"

    def __init__(self, key_rotator: KeyRotator, base_url: str | None = None):
        self._keys = key_rotator
        self._base_url = (base_url or settings.agnes_base_url).rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AgnesClient":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *exc):
        if self._session:
            await self._session.close()

    def _session_or_raise(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("AgnesClient chưa mở session — dùng `async with AgnesClient(...) as client:`")
        return self._session

    async def _headers(self, throttled: bool = True) -> tuple[dict, str]:
        # throttled=True: dùng cho generate ảnh/video — TỰ CHỜ đủ cooldown (3-5 phút,
        #   tự tăng nếu vẫn lỗi) trước khi trả key, vì đây là endpoint nặng, tốn tài
        #   nguyên server free.
        # throttled=False: dùng cho poll trạng thái — endpoint nhẹ, không cần chờ.
        key = await (self._keys.acquire_key() if throttled else self._keys.acquire_key_light())
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, key

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _post(self, path: str, payload: dict) -> dict:
        session = self._session_or_raise()
        headers, key = await self._headers(throttled=True)
        url = f"{self._base_url}{path}"
        async with session.post(url, headers=headers, data=json.dumps(payload)) as resp:
            if resp.status == 429:
                await self._keys.report_rate_limited(key)
                raise RateLimitError(f"429 tại {path}")
            if resp.status in (401, 403):
                await self._keys.mark_bad(key)
                raise AgnesAPIError(f"Key ...{key[-4:]} bị từ chối ({resp.status}) tại {path}")
            if resp.status >= 500:
                await self._keys.report_rate_limited(key)
                raise RateLimitError(f"{resp.status} server busy tại {path}")
            if resp.status >= 400:
                text = await resp.text()
                raise AgnesAPIError(f"Lỗi {resp.status} tại {path}: {text}")
            data = await resp.json()
            await self._keys.report_success(key)
            return data

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=settings.poll_max_backoff_sec),
        reraise=True,
    )
    async def _get(self, path: str, params: dict) -> dict:
        session = self._session_or_raise()
        headers, key = await self._headers(throttled=False)
        url = f"{self._base_url}{path}"
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 429:
                await self._keys.report_rate_limited(key)
                raise RateLimitError(f"429 rate-limit khi poll {path}")
            if resp.status >= 500:
                await self._keys.report_rate_limited(key)
                raise RateLimitError(f"{resp.status} server busy khi poll {path}")
            if resp.status >= 400:
                text = await resp.text()
                raise AgnesAPIError(f"Lỗi {resp.status} khi poll {path}: {text}")
            data = await resp.json()
            await self._keys.report_success(key)
            return data

    # ---------------------------------------------------------------- vision

    async def analyze_image(self, image_path_or_url: str, question: str) -> str:
        payload = {
            "model": self.CHAT_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": image_path_or_url}},
                    ],
                }
            ],
        }
        data = await self._post("/v1/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------ planning

    async def plan_scenes(self, script_text: str, style_hint: str = "") -> list[dict]:
        system_prompt = (
            "Bạn là biên kịch/đạo diễn video ngắn. Chia kịch bản sau thành các scene. "
            "Trả lời DUY NHẤT bằng JSON hợp lệ, không thêm chữ nào khác, đúng dạng:\n"
            '[{"index": 1, "description": "...", "duration_sec": 4, "camera_move": "..."}]'
        )
        payload = {
            "model": self.CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Style: {style_hint}\n\nKịch bản:\n{script_text}"},
            ],
        }
        data = await self._post("/v1/chat/completions", payload)
        raw = data["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            scenes = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AgnesAPIError(f"Scene planner trả về JSON không hợp lệ: {raw[:300]}") from e
        return scenes

    # -------------------------------------------------------------- image

    async def generate_image(
        self,
        prompt: str,
        ratio: str = "9:16",
        size: str = "2K",
        reference_images: list[str] | None = None,
    ) -> ImageResult:
        payload: dict = {
            "model": self.IMAGE_MODEL,
            "prompt": prompt,
            "size": size,
            "ratio": ratio,
            "extra_body": {"response_format": "url"},
        }
        if reference_images:
            payload["extra_body"]["image"] = reference_images
        data = await self._post("/v1/images/generations", payload)
        url = data["data"][0]["url"]
        return ImageResult(url_or_path=url, is_local_path=False)

    # -------------------------------------------------------------- video

    async def submit_video_task(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
    ) -> str:
        num_frames = nearest_valid_num_frames(num_frames)
        payload: dict = {
            "model": self.VIDEO_MODEL,
            "prompt": prompt,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }
        extra_body: dict = {}
        if images:
            extra_body["image"] = images
            extra_body["mode"] = mode
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if extra_body:
            payload["extra_body"] = extra_body

        data = await self._post("/v1/videos", payload)
        video_id = data.get("id") or data.get("video_id")
        if not video_id:
            raise AgnesAPIError(f"Không tìm thấy video_id trong response: {data}")
        log.info(f"Đã submit video task {video_id} (mode={mode}, num_frames={num_frames})")
        return video_id

    async def poll_video_task(self, video_id: str) -> VideoTaskHandle:
        data = await self._get("/agnesapi", {"video_id": video_id})
        status_raw = data.get("status", "queued")
        status_map = {
            "queued": VideoStatus.QUEUED,
            "pending": VideoStatus.QUEUED,
            "in_progress": VideoStatus.IN_PROGRESS,
            "processing": VideoStatus.IN_PROGRESS,
            "completed": VideoStatus.COMPLETED,
            "succeeded": VideoStatus.COMPLETED,
            "failed": VideoStatus.FAILED,
            "error": VideoStatus.FAILED,
        }
        status = status_map.get(status_raw, VideoStatus.IN_PROGRESS)
        handle = VideoTaskHandle(video_id=video_id, status=status)
        if status == VideoStatus.COMPLETED:
            handle.result_url = (data.get("metadata") or {}).get("url") or data.get("url")
        if status == VideoStatus.FAILED:
            handle.error = data.get("error") or "unknown error"
        return handle

    async def download_video(self, video_url: str, dest_path: str) -> str:
        session = self._session_or_raise()
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        async with session.get(video_url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    f.write(chunk)
        log.info(f"Đã tải video -> {dest_path}")
        return dest_path
