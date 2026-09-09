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
import random
import ssl
from pathlib import Path

import aiohttp
import certifi
from config import settings
from models.image_request import ImageGenerationRequest, ImageReference, normalize_image_ratio, normalize_image_resolution
from engines.base_engine import (
    BaseEngine,
    EngineCapabilities,
    ImageResult,
    VideoStatus,
    VideoTaskHandle,
)
from utils.key_rotation import KeyRotator, NoAvailableKeyError
from utils.logger import get_logger
from engines.agnes_errors import classify_status, AgnesErrorKind

log = get_logger(__name__)


class RateLimitError(Exception):
    pass


class AgnesAPIError(Exception):
    def __init__(self, message: str, kind: AgnesErrorKind = AgnesErrorKind.UNKNOWN):
        super().__init__(message)
        self.kind = kind


def nearest_valid_num_frames(target: int) -> int:
    """Ép num_frames về đúng luật 8n+1 (n nguyên), giới hạn [1, 441]."""
    target = max(1, min(441, target))
    n = round((target - 1) / 8)
    value = 8 * n + 1
    return max(1, min(441, value))


def video_dimensions_for_ratio(ratio: str, *, resolution: str = "720p") -> tuple[int, int]:
    """Return a native Agnes V2.0 canvas for the requested aspect ratio.

    V2.0 is a width/height contract; never generate landscape and crop it later
    when the requested platform is portrait. The API normalizes these dimensions
    to its supported resolution tier.
    """
    ratio = (ratio or "9:16").strip()
    tiers = {
        "480p": {
            "16:9": (854, 480), "9:16": (480, 854), "1:1": (480, 480),
            "4:3": (640, 480), "3:4": (480, 640),
        },
        "720p": {
            "16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720),
            "4:3": (960, 720), "3:4": (720, 960),
        },
        "1080p": {
            "16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080),
            "4:3": (1440, 1080), "3:4": (1080, 1440),
        },
    }
    tier = (resolution or "720p").strip().lower()
    if tier not in tiers:
        tier = "720p"
    try:
        return tiers[tier][ratio]
    except KeyError as exc:
        raise ValueError(f"Unsupported video aspect ratio: {ratio!r}") from exc


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

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Parse the common numeric Retry-After form; return None for unsupported forms."""
        if not value:
            return None
        try:
            return max(0.0, float(value.strip()))
        except (TypeError, ValueError):
            return None

    def _retry_delay(self, attempt: int, *, retry_after: float | None = None) -> float:
        """Bounded exponential backoff with small jitter.

        ``attempt`` is zero-based and represents the failed attempt. Server-provided
        Retry-After is honoured but capped so a broken gateway cannot park a job for
        minutes/hours.
        """
        if retry_after is not None:
            base = min(retry_after, settings.agnes_retry_429_max_delay_sec)
        else:
            base = min(
                settings.agnes_retry_max_delay_sec,
                settings.agnes_retry_initial_delay_sec * (2 ** attempt),
            )
        jitter = random.uniform(0.0, settings.agnes_retry_jitter_sec) if settings.agnes_retry_jitter_sec else 0.0
        return min(settings.agnes_retry_max_delay_sec, base + jitter)

    async def _headers_retry(self, excluded_keys: set[str]) -> tuple[dict, str]:
        try:
            key = await self._keys.acquire_key_light(exclude_keys=excluded_keys)
        except TypeError:
            # Backward-compatible with lightweight test doubles / older rotators.
            key = await self._keys.acquire_key_light()
        except NoAvailableKeyError:
            # No alternate key exists. Reuse the failed-but-still-valid key after the
            # bounded backoff. If every key is actually marked bad, this second call
            # raises NoAvailableKeyError and we fail clearly instead of resurrecting it.
            try:
                key = await self._keys.acquire_key_light()
            except NoAvailableKeyError as exc:
                raise AgnesAPIError(
                    "Tất cả Agnes API key khả dụng đã bị từ chối hoặc không còn khả dụng để retry.",
                    AgnesErrorKind.AUTH,
                ) from exc
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, key

    async def _post(self, path: str, payload: dict, *, throttled: bool = True) -> dict:
        """POST with bounded production retry semantics.

        Retry matrix:
        - 401/403: mark the key bad and immediately try another key.
        - 429: mark rate-limited, then bounded backoff + key rotation.
        - 5xx (including Agnes 520): transient server failure; bounded backoff,
          but NEVER increase the key's rate-limit cooldown.
        - network/timeout: bounded backoff + another key when available.
        - other 4xx: fail immediately; these are normally request/config errors.
        """
        session = self._session_or_raise()
        excluded_keys: set[str] = set()
        last_error: Exception | None = None

        for attempt in range(settings.agnes_retry_max_attempts):
            if attempt == 0:
                headers, key = await self._headers(throttled=throttled)
            else:
                headers, key = await self._headers_retry(excluded_keys)
            url = f"{self._base_url}{path}"

            try:
                async with session.post(url, headers=headers, data=json.dumps(payload)) as resp:
                    if resp.status == 401 or resp.status == 403:
                        await self._keys.mark_bad(key)
                        excluded_keys.add(key)
                        last_error = AgnesAPIError(
                            f"Key ...{key[-4:]} bị từ chối ({resp.status}) tại {path}",
                            classify_status(resp.status),
                        )
                        if attempt + 1 < settings.agnes_retry_max_attempts:
                            log.warning(
                                "Agnes auth failure %s trên key ...%s; chuyển key khác (%d/%d)",
                                resp.status, key[-4:], attempt + 1, settings.agnes_retry_max_attempts,
                            )
                            continue
                        raise last_error

                    if resp.status == 429:
                        await self._keys.report_rate_limited(key)
                        excluded_keys.add(key)
                        retry_after = self._parse_retry_after(resp.headers.get("Retry-After"))
                        last_error = AgnesAPIError(
                            f"429 rate-limit tại {path}", AgnesErrorKind.RATE_LIMIT
                        )
                        if attempt + 1 < settings.agnes_retry_max_attempts:
                            delay = self._retry_delay(attempt, retry_after=retry_after)
                            log.warning(
                                "Agnes 429 tại %s; retry sau %.1fs (%d/%d)",
                                path, delay, attempt + 1, settings.agnes_retry_max_attempts,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise last_error

                    if 500 <= resp.status < 600:
                        excluded_keys.add(key)
                        text = await resp.text()
                        last_error = AgnesAPIError(
                            f"{resp.status} server busy tại {path}: {text[:500]}",
                            AgnesErrorKind.SERVER,
                        )
                        if attempt + 1 < settings.agnes_retry_max_attempts:
                            delay = self._retry_delay(attempt)
                            log.warning(
                                "Agnes %s tại %s; retry sau %.1fs (%d/%d)",
                                resp.status, path, delay, attempt + 1, settings.agnes_retry_max_attempts,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise last_error

                    if resp.status >= 400:
                        text = await resp.text()
                        raise AgnesAPIError(
                            f"Lỗi {resp.status} tại {path}: {text}",
                            classify_status(resp.status),
                        )

                    data = await resp.json()
                    await self._keys.report_success(key)
                    return data

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                excluded_keys.add(key)
                last_error = AgnesAPIError(
                    f"{type(exc).__name__} tại {path}: {exc}",
                    AgnesErrorKind.TIMEOUT if isinstance(exc, asyncio.TimeoutError) else AgnesErrorKind.NETWORK,
                )
                if attempt + 1 < settings.agnes_retry_max_attempts:
                    delay = self._retry_delay(attempt)
                    log.warning(
                        "Agnes %s tại %s; retry sau %.1fs (%d/%d)",
                        type(exc).__name__, path, delay, attempt + 1, settings.agnes_retry_max_attempts,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error from exc

        if last_error:
            raise last_error
        raise AgnesAPIError(f"Request Agnes thất bại tại {path}")

    async def _get(self, path: str, params: dict, *, root_path: bool = False) -> dict:
        """GET/poll with a shorter bounded retry budget than generation POSTs."""
        session = self._session_or_raise()
        excluded_keys: set[str] = set()
        last_error: Exception | None = None
        max_attempts = min(3, settings.agnes_retry_max_attempts)
        base = self._root_url if root_path else self._base_url
        url = f"{base}{path}"

        for attempt in range(max_attempts):
            if attempt == 0:
                headers, key = await self._headers(throttled=False)
            else:
                headers, key = await self._headers_retry(excluded_keys)
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status in (401, 403):
                        await self._keys.mark_bad(key)
                        excluded_keys.add(key)
                        last_error = AgnesAPIError(
                            f"Key ...{key[-4:]} bị từ chối ({resp.status}) khi poll {path}",
                            AgnesErrorKind.AUTH,
                        )
                    elif resp.status == 429:
                        await self._keys.report_rate_limited(key)
                        excluded_keys.add(key)
                        last_error = AgnesAPIError(
                            f"429 rate-limit khi poll {path}", AgnesErrorKind.RATE_LIMIT
                        )
                    elif 500 <= resp.status < 600:
                        excluded_keys.add(key)
                        last_error = AgnesAPIError(
                            f"{resp.status} server busy khi poll {path}", AgnesErrorKind.SERVER
                        )
                    elif resp.status >= 400:
                        text = await resp.text()
                        raise AgnesAPIError(
                            f"Lỗi {resp.status} khi poll {path}: {text}",
                            classify_status(resp.status),
                        )
                    else:
                        data = await resp.json()
                        await self._keys.report_success(key)
                        return data

                    if attempt + 1 < max_attempts:
                        delay = self._retry_delay(attempt)
                        log.warning(
                            "Agnes poll retry sau %.1fs (%d/%d)",
                            delay, attempt + 1, max_attempts,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise last_error
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                excluded_keys.add(key)
                last_error = AgnesAPIError(
                    f"{type(exc).__name__} khi poll {path}: {exc}",
                    AgnesErrorKind.TIMEOUT if isinstance(exc, asyncio.TimeoutError) else AgnesErrorKind.NETWORK,
                )
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                raise last_error from exc

        if last_error:
            raise last_error
        raise AgnesAPIError(f"Poll Agnes thất bại tại {path}")

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
        aspect_ratio: str = "9:16",
    ) -> str:
        model_name = model or settings.agnes_models.video
        aspect_ratio = (aspect_ratio or "9:16").strip()
        normalized_model = model_name.lower().strip()
        is_v25_flash = normalized_model == "agnes-video-2.5-flash"

        if is_v25_flash:
            # Agnes Video 2.5 Flash contract is NOT the V2.0 contract:
            # mode/images/first_frame/last_frame are top-level fields.
            if images and len(images) > 5:
                raise ValueError("Agnes Video 2.5 Flash chỉ nhận tối đa 5 ảnh reference")

            requested_seconds = str(seconds or "5")
            try:
                sec_value = float(requested_seconds)
            except ValueError as exc:
                raise ValueError("seconds của Agnes Video 2.5 Flash phải là số") from exc
            if not 4 <= sec_value <= 12:
                raise ValueError(
                    f"Agnes Video 2.5 Flash chỉ hỗ trợ seconds từ 4 đến 12, nhận {requested_seconds}"
                )

            api_mode = "reference" if images else "text"
            payload: dict = {
                "model": model_name,
                "prompt": prompt,
                "seconds": (
                    str(int(sec_value)) if sec_value.is_integer()
                    else str(sec_value)
                ),
                "mode": api_mode,
                "size": "720P",
                "aspect_ratio": aspect_ratio,
                "n": 1,
            }
            if images:
                payload["images"] = images[:5]
            if negative_prompt:
                payload["prompt"] = f"{prompt}\nAvoid: {negative_prompt}"

        else:
            # Agnes Video V2.0 uses width/height + 8n+1 frames.
            num_frames = nearest_valid_num_frames(num_frames)
            width, height = video_dimensions_for_ratio(
                aspect_ratio, resolution="720p"
            )
            payload = {
                "model": model_name,
                "prompt": prompt,
                "num_frames": num_frames,
                "frame_rate": frame_rate,
                "width": width,
                "height": height,
            }
            if images:
                payload["extra_body"] = {
                    "image": images,
                    "mode": mode,
                }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt

        data = await self._post(
            settings.agnes_endpoints.video_submit, payload, throttled=True
        )
        video_id = data.get("video_id") or data.get("id") or data.get("task_id")
        if not video_id:
            raise AgnesAPIError(f"Không tìm thấy video_id trong response: {data}")
        log.info(
            "Đã submit video task %s (model=%s, mode=%s, generated=%ss)",
            video_id, model_name, payload.get("mode", mode), payload.get("seconds", "?"),
        )
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
