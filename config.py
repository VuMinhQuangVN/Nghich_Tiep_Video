"""
config.py
---------
Đọc .env, expose 1 object Settings duy nhất cho toàn bộ app.
Không đặt logic nghiệp vụ ở đây — chỉ đọc & validate cấu hình (SRP).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _split_keys(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _normalize_agnes_base_url(raw: str | None) -> str:
    """Return Agnes API base URL in canonical ``.../v1`` form."""
    value = (raw or "https://apihub.agnes-ai.com/v1").strip().rstrip("/")
    if not value:
        value = "https://apihub.agnes-ai.com/v1"
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


@dataclass(frozen=True)
class AgnesModelConfig:
    """Centralized Agnes model IDs and feature flags."""

    text: str = os.getenv("AGNES_TEXT_MODEL", "agnes-2.5-flash")
    image: str = os.getenv("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash")
    video: str = os.getenv("AGNES_VIDEO_MODEL", "agnes-video-v2.0")
    video_experimental: str = os.getenv(
        "AGNES_VIDEO_EXPERIMENTAL_MODEL", "agnes-video-2.5-flash"
    )
    video_trial: str = os.getenv("AGNES_VIDEO_25_MODEL", "agnes-video-2.5")
    video_experimental_enabled: bool = os.getenv(
        "AGNES_VIDEO_EXPERIMENTAL", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    video_trial_enabled: bool = os.getenv(
        "AGNES_VIDEO_25_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AgnesEndpointConfig:
    """Centralized relative API paths below ``AGNES_BASE_URL``."""

    chat_completions: str = os.getenv("AGNES_CHAT_ENDPOINT", "/chat/completions")
    image_generations: str = os.getenv("AGNES_IMAGE_ENDPOINT", "/images/generations")
    video_submit: str = os.getenv("AGNES_VIDEO_ENDPOINT", "/videos")
    video_poll: str = os.getenv("AGNES_VIDEO_POLL_ENDPOINT", "/agnesapi")


@dataclass(frozen=True)
class AgnesCapabilityConfig:
    """Centralized capabilities for the stable Agnes video engine."""

    supports_storyboard_read: bool = False
    supports_keyframe_array: bool = True
    supports_edit: bool = False
    supports_image_to_video: bool = True
    supports_text_to_video: bool = True
    max_clip_duration_sec: float = 18
    min_clip_duration_sec: float = 1


@dataclass(frozen=True)
class Settings:

    agnes_api_keys: list[str] = field(default_factory=lambda: _split_keys(os.getenv("AGNES_API_KEYS")))
    agnes_base_url: str = _normalize_agnes_base_url(os.getenv("AGNES_BASE_URL"))
    agnes_request_timeout_sec: float = float(os.getenv("AGNES_REQUEST_TIMEOUT_SEC", "120"))
    agnes_alternate_base_url: str = _normalize_agnes_base_url(
        os.getenv("AGNES_ALTERNATE_BASE_URL")
    ) if os.getenv("AGNES_ALTERNATE_BASE_URL") else ""
    agnes_models: AgnesModelConfig = field(default_factory=AgnesModelConfig)
    agnes_endpoints: AgnesEndpointConfig = field(default_factory=AgnesEndpointConfig)
    agnes_capabilities: AgnesCapabilityConfig = field(default_factory=AgnesCapabilityConfig)

    # Server free -> giới hạn thật là TỐC ĐỘ request, không phải quota. Nên mặc định
    # concurrency = 1 (không bắn song song), nghỉ (cooldown) giữa các lần generate.
    max_concurrent_image_requests: int = int(os.getenv("MAX_CONCURRENT_IMAGE_REQUESTS", "1"))
    max_concurrent_video_submit: int = int(os.getenv("MAX_CONCURRENT_VIDEO_SUBMIT", "1"))
    poll_interval_sec: float = float(os.getenv("POLL_INTERVAL_SEC", "4"))
    poll_max_backoff_sec: float = float(os.getenv("POLL_MAX_BACKOFF_SEC", "60"))

    # Cooldown giữa 2 lần GENERATE (ảnh/video) liên tiếp trên cùng 1 key.
    # Mặc định 3 phút, tự tăng dần nếu vẫn gặp lỗi (adaptive), trần 15 phút.
    cooldown_base_sec: float = float(os.getenv("COOLDOWN_BASE_SEC", "180"))
    cooldown_max_sec: float = float(os.getenv("COOLDOWN_MAX_SEC", "900"))
    cooldown_step_sec: float = float(os.getenv("COOLDOWN_STEP_SEC", "60"))
    cooldown_decay_after_success: int = int(os.getenv("COOLDOWN_DECAY_AFTER_SUCCESS", "3"))

    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    cache_dir: Path = Path(os.getenv("CACHE_DIR", "./cache"))

    def validate(self) -> None:
        if not self.agnes_api_keys:
            raise RuntimeError(
                "Chưa có AGNES_API_KEYS trong .env. Copy .env.example thành .env rồi điền key thật."
            )
        if not self.agnes_base_url.startswith("https://"):
            raise RuntimeError("AGNES_BASE_URL phải dùng HTTPS.")
        if self.agnes_request_timeout_sec <= 0:
            raise RuntimeError("AGNES_REQUEST_TIMEOUT_SEC phải lớn hơn 0.")
        if self.agnes_alternate_base_url and not self.agnes_alternate_base_url.startswith("https://"):
            raise RuntimeError("AGNES_ALTERNATE_BASE_URL phải dùng HTTPS.")
        for name, value in vars(self.agnes_models).items():
            if isinstance(value, str) and not value.strip():
                raise RuntimeError(f"Cấu hình Agnes model {name} không được để trống.")
        for name, value in vars(self.agnes_endpoints).items():
            if not value.startswith("/"):
                raise RuntimeError(f"Endpoint Agnes {name} phải là path bắt đầu bằng '/'.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
