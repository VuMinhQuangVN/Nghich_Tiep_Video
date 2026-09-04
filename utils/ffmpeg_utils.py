"""
utils/ffmpeg_utils.py
----------------------
Wrapper mỏng quanh ffmpeg CLI (yêu cầu ffmpeg đã cài trên máy & có trong PATH).
Chỉ 2 việc: (1) trích frame cuối 1 video ra ảnh, (2) ghép nhiều video theo
thứ tự thành 1 file cuối. Không chứa logic nghiệp vụ khác (SRP).
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)


def ensure_ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Không tìm thấy ffmpeg trong PATH. Cài đặt: "
            "Ubuntu/Debian `sudo apt install ffmpeg`, "
            "macOS `brew install ffmpeg`, "
            "Windows: tải từ ffmpeg.org rồi thêm vào PATH."
        )


async def extract_last_frame(video_path: Path, out_image_path: Path) -> Path:
    """Trích frame cuối cùng của video thành ảnh PNG (chạy nền, không block)."""
    out_image_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-sseof", "-1",
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_image_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trích frame cuối thất bại: {stderr.decode(errors='ignore')}")
    log.info(f"Đã trích frame cuối: {out_image_path}")
    return out_image_path


async def concat_videos(video_paths: list[Path], out_path: Path) -> Path:
    """Ghép nhiều video theo đúng thứ tự trong list thành 1 file mp4 cuối."""
    if not video_paths:
        raise ValueError("Danh sách video rỗng, không có gì để ghép")
    if len(video_paths) == 1:
        shutil.copy(video_paths[0], out_path)
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.parent / f"_concat_list_{out_path.stem}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in video_paths:
            f.write(f"file '{p.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    list_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        # fallback: re-encode nếu codec giữa các đoạn không khớp để "-c copy" chạy được
        log.warning("Ghép nhanh (-c copy) thất bại, thử lại với re-encode...")
        return await _concat_with_reencode(video_paths, out_path)
    log.info(f"Đã ghép {len(video_paths)} video -> {out_path}")
    return out_path


async def _concat_with_reencode(video_paths: list[Path], out_path: Path) -> Path:
    list_file = out_path.parent / f"_concat_list_re_{out_path.stem}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in video_paths:
            f.write(f"file '{p.resolve()}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-c:a", "aac",
        str(out_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    list_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg ghép video thất bại: {stderr.decode(errors='ignore')}")
    log.info(f"Đã ghép (re-encode) {len(video_paths)} video -> {out_path}")
    return out_path
