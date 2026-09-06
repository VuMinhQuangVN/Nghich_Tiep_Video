"""
engines/agnes_client.py
-------------------------
Implement BaseEngine cho Agnes AI.

Base URL chuẩn: https://apihub.agnes-ai.com/v1
- agnes-2.5-flash          -> /chat/completions   (text + vision)
- agnes-image-2.1-flash    -> /images/generations (text-to-image / image-to-image)
- agnes-video-v2.0         -> /videos (submit, async) + GET /agnesapi?video_id=...(poll)

Điểm quan trọng đã theo đúng docs:
- response_format & mode/image nằm trong extra_body, KHÔNG ở top-level.
- num_frames phải theo luật 8n+1, tối đa 441.
- Có key rotation + retry với tenacity khi gặp 429/503.
"""
from __future__ import annotations

import asyncio
import json
import ssl
from pathlib import Path

import aiohttp
import certifi
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from models.image_request import ImageGenerationRequest, ImageReference, normalize_image_ratio, normalize_image_resolution
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
    """Agnes adapter using centralized model/endpoint/capability config."""

    def __init__(self, key_rotator: KeyRotator, base_url: str | None = None):
        self._keys = key_rotator
        self._base_url = self._normalize_base_url(base_url or settings.agnes_base_url)
        self._root_url = self._base_url.removesuffix("/v1")
        self._session: aiohttp.ClientSession | None = None
        self.capabilities = EngineCapabilities(**vars(settings.agnes_capabilities))

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        value = base_url.strip().rstrip("/")
        if not value:
            raise ValueError("Agnes base URL không được để trống")
        if not value.startswith("https://"):
            raise ValueError("Agnes base URL phải dùng HTTPS")
        if not value.endswith("/v1"):
            value = f"{value}/v1"
        return value

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        # Windows/Python có thể không dùng đúng CA bundle hệ thống cho aiohttp.
        # Dùng certifi để HTTPS verification ổn định, tuyệt đối không disable verify.
        return ssl.create_default_context(cafile=certifi.where())

    async def __aenter__(self) -> "AgnesClient":
        timeout = aiohttp.ClientTimeout(total=settings.agnes_request_timeout_sec)
        connector = aiohttp.TCPConnector(ssl=self._ssl_context())
        self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self

    async def __aexit__(self, *exc):
        if self._session:
            await self._session.close()
            self._session = None

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
    async def _post(self, path: str, payload: dict, *, throttled: bool = True) -> dict:
        session = self._session_or_raise()
        headers, key = await self._headers(throttled=throttled)
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
    async def _get(self, path: str, params: dict, *, root_path: bool = False) -> dict:
        session = self._session_or_raise()
        headers, key = await self._headers(throttled=False)
        base = self._root_url if root_path else self._base_url
        url = f"{base}{path}"
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
            "model": settings.agnes_models.text,
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
        data = await self._post(settings.agnes_endpoints.chat_completions, payload, throttled=False)
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------ planning

    async def plan_scenes(self, script_text: str, style_hint: str = "") -> list[dict]:
        system_prompt = (
            "Bạn là biên kịch/đạo diễn video ngắn. Chia kịch bản sau thành các scene. "
            "Trả lời DUY NHẤT bằng JSON hợp lệ, không thêm chữ nào khác, đúng dạng:\n"
            '[{"index": 1, "description": "...", "duration_sec": 4, "camera_move": "..."}]'
        )
        payload = {
            "model": settings.agnes_models.text,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Style: {style_hint}\n\nKịch bản:\n{script_text}"},
            ],
        }
        data = await self._post(settings.agnes_endpoints.chat_completions, payload, throttled=False)
        raw = data["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            scenes = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AgnesAPIError(f"Scene planner trả về JSON không hợp lệ: {raw[:300]}") from e
        return scenes

    # -------------------------------------------------------------- image

    async def generate_image_request(self, request: ImageGenerationRequest) -> ImageResult:
        request.validate()
        payload: dict = {
            "model": settings.agnes_models.image,
            "prompt": request.prompt.strip(),
            "size": normalize_image_resolution(request.resolution),
            "ratio": normalize_image_ratio(request.ratio),
            "extra_body": {"response_format": "url"},
        }
        references = request.reference_values()
        if references:
            payload["extra_body"]["image"] = references
        data = await self._post(settings.agnes_endpoints.image_generations, payload, throttled=True)
        item = data["data"][0]
        url = item.get("url")
        if url:
            return ImageResult(url_or_path=url, is_local_path=False)
        b64 = item.get("b64_json")
        if b64:
            return ImageResult(url_or_path=f"data:image/png;base64,{b64}", is_local_path=False)
        raise AgnesAPIError(f"Image API không trả url/b64_json: {data}")

    async def generate_image(
        self,
        prompt: str,
        ratio: str = "9:16",
        size: str = "2K",
        reference_images: list[str] | None = None,
    ) -> ImageResult:
        request = ImageGenerationRequest(
            prompt=prompt,
            ratio=ratio,
            resolution=size,
            references=[ImageReference(value=value) for value in (reference_images or [])],
        )
        return await self.generate_image_request(request)

    # -------------------------------------------------------------- video

    async def submit_video_task(
        self,
        prompt: str,
        images: list[str] | None = None,
        mode: str = "ti2vid",
        num_frames: int = 121,
        frame_rate: int = 24,
        negative_prompt: str | None = None,
        *,
        model: str | None = None,
        size: str | None = None,
        seconds: str | None = None,
        n: int | None = None,
    ) -> str:
        num_frames = nearest_valid_num_frames(num_frames)
        payload: dict = {
            "model": model or settings.agnes_models.video,
            "prompt": prompt,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }
        if size is not None:
            payload["size"] = size
        if seconds is not None:
            payload["seconds"] = seconds
        if n is not None:
            payload["n"] = n
        extra_body: dict = {}
        if images:
            extra_body["image"] = images
            extra_body["mode"] = mode
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if extra_body:
            payload["extra_body"] = extra_body

        data = await self._post(settings.agnes_endpoints.video_submit, payload, throttled=True)
        video_id = data.get("video_id") or data.get("id") or data.get("task_id")
        if not video_id:
            raise AgnesAPIError(f"Không tìm thấy video_id trong response: {data}")
        log.info(f"Đã submit video task {video_id} (model={payload['model']}, mode={mode})")
        return video_id

    async def poll_video_task(self, video_id: str, *, model_name: str | None = None) -> VideoTaskHandle:
        params = {"video_id": video_id}
        if model_name:
            params["model_name"] = model_name
        data = await self._get(settings.agnes_endpoints.video_poll, params, root_path=True)
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
        handle = VideoTaskHandle(
            video_id=video_id,
            status=status,
            metadata=dict(data.get("metadata") or {}),
        )
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
