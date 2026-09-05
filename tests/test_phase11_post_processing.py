from pathlib import Path

import pytest

from utils.video_post_processor import PostProcessOptions, TextOverlay, VideoPostProcessor


def test_no_options_is_safe_noop(tmp_path):
    src = tmp_path / "generated.mp4"
    out = tmp_path / "final.mp4"
    src.write_bytes(b"fake-video")

    result = __import__("asyncio").run(VideoPostProcessor().process(src, out))

    assert result == out
    assert out.read_bytes() == src.read_bytes()


def test_has_work_detects_all_supported_operations(tmp_path):
    p = VideoPostProcessor()
    assert not p.has_work(PostProcessOptions())
    assert p.has_work(PostProcessOptions(voiceover_path=tmp_path / "v.wav"))
    assert p.has_work(PostProcessOptions(background_music_path=tmp_path / "m.mp3"))
    assert p.has_work(PostProcessOptions(subtitles_path=tmp_path / "s.srt"))
    assert p.has_work(PostProcessOptions(text_overlays=[TextOverlay("hello")]))
    assert p.has_work(PostProcessOptions(cta="Buy now"))


def test_missing_input_media_is_rejected(tmp_path):
    src = tmp_path / "generated.mp4"
    src.write_bytes(b"fake-video")
    with pytest.raises(FileNotFoundError, match="voiceover"):
        __import__("asyncio").run(
            VideoPostProcessor().process(
                src, tmp_path / "out.mp4",
                PostProcessOptions(voiceover_path=tmp_path / "missing.wav"),
            )
        )


def test_overlay_validation():
    with pytest.raises(ValueError, match="end_sec"):
        __import__("asyncio").run(
            VideoPostProcessor().process(
                Path(__file__), Path(__file__).with_name("unused.mp4"),
                PostProcessOptions(text_overlays=[TextOverlay("x", 2, 1)]),
            )
        )
