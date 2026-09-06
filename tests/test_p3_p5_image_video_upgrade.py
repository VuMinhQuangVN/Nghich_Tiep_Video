from pathlib import Path

import pytest

import config
from engines.agnes_client import AgnesClient
from engines.agnes_video_25_flash import AgnesVideo25FlashAdapter
from engines.agnes_video_v20 import AgnesVideoV20Adapter
from engines.fallback_video_engine import FallbackVideoEngine
from engines.agnes_video_factory import build_agnes_video_engine
from engines.base_engine import VideoStatus, VideoTaskHandle
from models.image_request import (
    ImageGenerationRequest,
    ImageReference,
    image_ratio_for_platform,
    normalize_image_ratio,
    normalize_image_resolution,
)
from models.video_job import VideoJob, VideoJobStatus


class DummyKeys:
    async def acquire_key(self):
        return "test-key"

    async def acquire_key_light(self):
        return "test-key"


class FakeClient:
    def __init__(self):
        self.submit_calls = []
        self.poll_calls = []
        self.download_calls = []
        self.next_id = 0
        self.poll_status = VideoStatus.COMPLETED

    async def submit_video_task(self, **kwargs):
        self.submit_calls.append(kwargs)
        self.next_id += 1
        return f"video-{self.next_id}"

    async def poll_video_task(self, video_id, *, model_name=None):
        self.poll_calls.append((video_id, model_name))
        return VideoTaskHandle(
            video_id=video_id,
            status=self.poll_status,
            result_url="https://example.com/video.mp4" if self.poll_status == VideoStatus.COMPLETED else None,
            error="boom" if self.poll_status == VideoStatus.FAILED else None,
            metadata={"size_mapping": {"resolution": "720p"}},
        )

    async def download_video(self, video_url, dest_path):
        self.download_calls.append((video_url, dest_path))
        Path(dest_path).write_bytes(b"fake")
        return dest_path


class FailingVideoEngine:
    def __init__(self):
        self.submit_calls = 0

    async def submit_video(self, *args, **kwargs):
        self.submit_calls += 1
        raise RuntimeError("experimental unavailable")

    async def poll_video(self, job):
        raise AssertionError("should not poll primary after failed submit")

    async def download_video(self, job, dest_path):
        raise AssertionError("should not download primary")


class StableVideoEngine:
    def __init__(self):
        self.submit_calls = 0
        self.poll_calls = 0

    async def submit_video(self, *args, **kwargs):
        self.submit_calls += 1
        return VideoJob(job_id="stable-1", model="agnes-video-v2.0")

    async def poll_video(self, job):
        self.poll_calls += 1
        return VideoJob(job_id=job.job_id, model=job.model, status=VideoJobStatus.COMPLETED, result_url="https://example.com/final.mp4")

    async def download_video(self, job, dest_path):
        Path(dest_path).write_bytes(b"fake")
        return dest_path


def test_image_request_supports_multiple_references_ratio_and_resolution():
    request = ImageGenerationRequest(
        prompt="product hero",
        ratio="9:16",
        resolution="3K",
        references=[
            ImageReference("https://example.com/front.png"),
            ImageReference("data:image/png;base64,AAA"),
        ],
    )
    assert request.reference_values() == [
        "https://example.com/front.png",
        "data:image/png;base64,AAA",
    ]
    request.validate()


def test_image_ratio_and_resolution_normalization():
    assert normalize_image_ratio("16:9") == "16:9"
    assert normalize_image_resolution("2k") == "2K"
    assert image_ratio_for_platform("TikTok") == "9:16"
    assert image_ratio_for_platform("YouTube") == "16:9"
    with pytest.raises(ValueError):
        normalize_image_ratio("5:7")
    with pytest.raises(ValueError):
        normalize_image_resolution("8K")


@pytest.mark.asyncio
async def test_image_client_sends_agnes_21_payload(monkeypatch):
    client = AgnesClient(DummyKeys(), "https://example.com/v1")
    captured = []

    async def fake_post(path, payload, *, throttled=True):
        captured.append((path, payload, throttled))
        return {"data": [{"url": "https://example.com/generated.png"}]}

    monkeypatch.setattr(client, "_post", fake_post)
    result = await client.generate_image(
        "hero",
        ratio="9:16",
        size="4K",
        reference_images=["https://example.com/a.png", "data:image/png;base64,AAA"],
    )
    assert result.url_or_path.endswith("generated.png")
    payload = captured[0][1]
    assert payload["model"] == "agnes-image-2.1-flash"
    assert payload["size"] == "4K"
    assert payload["ratio"] == "9:16"
    assert payload["extra_body"]["image"] == ["https://example.com/a.png", "data:image/png;base64,AAA"]


@pytest.mark.asyncio
async def test_v20_adapter_submit_poll_download(tmp_path):
    client = FakeClient()
    adapter = AgnesVideoV20Adapter(client)
    job = await adapter.submit_video("demo", ["https://example.com/a.png"], num_frames=121, frame_rate=24)
    assert job.model == config.settings.agnes_models.video
    assert job.job_id == "video-1"
    assert client.submit_calls[0]["model"] == "agnes-video-v2.0"

    job = await adapter.poll_video(job)
    assert job.completed
    assert client.poll_calls[-1] == ("video-1", "agnes-video-v2.0")
    dest = await adapter.download_video(job, str(tmp_path / "v20.mp4"))
    assert Path(dest).exists()


@pytest.mark.asyncio
async def test_v25_flash_adapter_uses_experimental_contract():
    client = FakeClient()
    adapter = AgnesVideo25FlashAdapter(client)
    job = await adapter.submit_video(
        "demo",
        ["a", "b"],
        num_frames=121,
        frame_rate=24,
    )
    call = client.submit_calls[0]
    assert call["model"] == "agnes-video-2.5-flash"
    assert call["size"] == "720P"
    assert call["seconds"] == "5"
    assert call["n"] == 1
    assert call["mode"] == "reference"
    assert job.metadata["size"] == "720P"


@pytest.mark.asyncio
async def test_v25_flash_rejects_more_than_five_references():
    adapter = AgnesVideo25FlashAdapter(FakeClient())
    with pytest.raises(ValueError, match="at most 5"):
        await adapter.submit_video("demo", [str(i) for i in range(6)], num_frames=121, frame_rate=24)


@pytest.mark.asyncio
async def test_v25_flash_rejects_duration_outside_four_to_twelve_seconds():
    adapter = AgnesVideo25FlashAdapter(FakeClient())
    with pytest.raises(ValueError, match="4-12"):
        await adapter.submit_video("demo", num_frames=72, frame_rate=24)


def test_video_factory_defaults_to_stable(monkeypatch):
    class Models:
        video_experimental_enabled = False

    class Settings: 
        agnes_models = Models()

    monkeypatch.setattr("engines.agnes_video_factory.settings", Settings())
    client = FakeClient()
    engine = build_agnes_video_engine(client)
    assert isinstance(engine, AgnesVideoV20Adapter)


def test_video_factory_can_enable_experimental_with_fallback(monkeypatch):
    class Models:
        video_experimental_enabled = True

    class Settings:
        agnes_models = Models()

    monkeypatch.setattr("engines.agnes_video_factory.settings", Settings())
    client = FakeClient()
    engine = build_agnes_video_engine(client)
    assert isinstance(engine, FallbackVideoEngine)
    assert isinstance(engine.primary, AgnesVideo25FlashAdapter)
    assert isinstance(engine.fallback, AgnesVideoV20Adapter)


@pytest.mark.asyncio
async def test_experimental_submit_falls_back_to_v20():
    primary = FailingVideoEngine()
    fallback = StableVideoEngine()
    engine = FallbackVideoEngine(primary, fallback)
    job = await engine.submit_video("demo", num_frames=121, frame_rate=24)
    assert job.model == "agnes-video-v2.0"
    assert primary.submit_calls == 1
    assert fallback.submit_calls == 1


@pytest.mark.asyncio
async def test_experimental_poll_failure_falls_back_to_v20():
    class Primary:
        async def submit_video(self, *args, **kwargs):
            return VideoJob(
                job_id="exp-1",
                model="agnes-video-2.5-flash",
                metadata={"prompt": "demo", "num_frames": 121, "frame_rate": 24},
            )

        async def poll_video(self, job):
            return VideoJob(job_id=job.job_id, model=job.model, status=VideoJobStatus.FAILED, error="quota")

        async def download_video(self, job, dest_path):
            raise AssertionError

    primary = Primary()
    fallback = StableVideoEngine()
    engine = FallbackVideoEngine(primary, fallback)
    primary_job = await engine.submit_video("demo", num_frames=121, frame_rate=24)
    fallback_job = await engine.poll_video(primary_job)
    assert fallback_job.model == "agnes-video-v2.0"
    assert fallback.submit_calls == 1
    completed = await engine.poll_video(fallback_job)
    assert completed.completed
