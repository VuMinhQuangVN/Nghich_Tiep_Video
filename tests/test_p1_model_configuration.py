import pytest

import config
from engines.agnes_client import AgnesClient


class DummyKeys:
    async def acquire_key(self):
        return "test-key"

    async def acquire_key_light(self):
        return "test-key"



def test_model_config_is_centralized():
    models = config.settings.agnes_models

    assert models.text == "agnes-2.5-flash"
    assert models.image == "agnes-image-2.1-flash"
    assert models.video == "agnes-video-v2.0"
    assert models.video_experimental == "agnes-video-2.5-flash"
    assert models.video_trial == "agnes-video-2.5"
    assert models.video_experimental_enabled is False
    assert models.video_trial_enabled is False


def test_endpoint_config_is_centralized():
    endpoints = config.settings.agnes_endpoints

    assert endpoints.chat_completions == "/chat/completions"
    assert endpoints.image_generations == "/images/generations"
    assert endpoints.video_submit == "/videos"
    assert endpoints.video_poll == "/agnesapi"


def test_capability_config_is_centralized_and_mapped_to_engine():
    expected = config.settings.agnes_capabilities
    client = AgnesClient(DummyKeys(), "https://example.com/v1")

    assert client.capabilities.supports_storyboard_read == expected.supports_storyboard_read
    assert client.capabilities.supports_keyframe_array == expected.supports_keyframe_array
    assert client.capabilities.supports_edit == expected.supports_edit
    assert client.capabilities.supports_image_to_video == expected.supports_image_to_video
    assert client.capabilities.supports_text_to_video == expected.supports_text_to_video
    assert client.capabilities.max_clip_duration_sec == expected.max_clip_duration_sec
    assert client.capabilities.min_clip_duration_sec == expected.min_clip_duration_sec


@pytest.mark.asyncio
async def test_client_uses_centralized_models_and_endpoints(monkeypatch):
    client = AgnesClient(DummyKeys(), "https://example.com/v1")
    captured = []

    async def fake_post(path, payload, *, throttled=True):
        captured.append((path, payload, throttled))
        if path == config.settings.agnes_endpoints.chat_completions:
            return {"choices": [{"message": {"content": "ok"}}]}
        if path == config.settings.agnes_endpoints.image_generations:
            return {"data": [{"url": "https://example.com/image.png"}]}
        return {"id": "video-1"}

    monkeypatch.setattr(client, "_post", fake_post)

    assert await client.analyze_image("https://example.com/ref.png", "describe") == "ok"
    await client.generate_image("prompt")
    assert await client.submit_video_task("prompt") == "video-1"

    assert captured[0][0] == config.settings.agnes_endpoints.chat_completions
    assert captured[0][1]["model"] == config.settings.agnes_models.text
    assert captured[1][0] == config.settings.agnes_endpoints.image_generations
    assert captured[1][1]["model"] == config.settings.agnes_models.image
    assert captured[2][0] == config.settings.agnes_endpoints.video_submit
    assert captured[2][1]["model"] == config.settings.agnes_models.video


def test_no_hardcoded_primary_model_constants_remain_in_agnes_client():
    source = open("engines/agnes_client.py", encoding="utf-8").read()

    assert 'CHAT_MODEL = "agnes-2.5-flash"' not in source
    assert 'IMAGE_MODEL = "agnes-image-2.1-flash"' not in source
    assert 'VIDEO_MODEL = "agnes-video-v2.0"' not in source
