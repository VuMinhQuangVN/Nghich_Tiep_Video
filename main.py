#!/usr/bin/env python3
"""
main.py
--------
CLI chạy local. Ví dụ:

  python main.py \
      --script script.txt \
      --style "cinematic, warm lighting, photographic" \
      --subject "cô gái tóc dài áo dài trắng" \
      --reference ./reference.jpg \
      --keep-character \
      --quota-mode tiet_kiem

Nếu không truyền --reference / --keep-character, pipeline chạy KHÔNG có
character-lock (dùng khi video không có nhân vật cố định xuyên suốt).

Chạy `python main.py --help` để xem đầy đủ tham số.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from config import settings
from core.router import QuotaMode
from engines.agnes_client import AgnesClient
from orchestrator.pipeline_runner import PipelineInput, PipelineRunner
from utils.ffmpeg_utils import ensure_ffmpeg_installed
from utils.key_rotation import KeyRotator
from utils.logger import get_logger

log = get_logger("main")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI Video Content Tool — chạy local (Agnes AI)")
    p.add_argument("--script", required=True, help="Đường dẫn file .txt chứa kịch bản, hoặc dùng - để nhập từ stdin")
    p.add_argument("--style", default="cinematic, natural lighting, photographic", help="Style chung cho toàn video")
    p.add_argument("--subject", default="chủ thể chính", help="Tên/mô tả ngắn chủ thể chính (dùng trong prompt video)")
    p.add_argument("--reference", default=None, help="URL hoặc đường dẫn public tới ảnh mẫu (bắt buộc nếu --keep-character)")
    p.add_argument("--keep-character", action="store_true", help="Bật giữ nhân vật nhất quán (chạy character-lock)")
    p.add_argument(
        "--quota-mode",
        choices=["tiet_kiem", "binh_thuong"],
        default="tiet_kiem",
        help="tiet_kiem = ít request nhất (keyframe_array); binh_thuong = kiểm soát kỹ từng scene (frame_to_frame_chain)",
    )
    p.add_argument("--output", default=None, help="Thư mục output (mặc định lấy từ .env OUTPUT_DIR)")
    return p.parse_args()


def read_script(path_str: str) -> str:
    if path_str == "-":
        return sys.stdin.read()
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file kịch bản: {path}")
    return path.read_text(encoding="utf-8")


async def main() -> None:
    args = parse_args()
    settings.validate()
    ensure_ffmpeg_installed()

    if args.keep_character and not args.reference:
        log.error("Đã bật --keep-character nhưng thiếu --reference (ảnh mẫu). Dừng lại.")
        sys.exit(1)

    script_text = read_script(args.script)
    quota_mode = QuotaMode.SAVE if args.quota_mode == "tiet_kiem" else QuotaMode.NORMAL
    output_dir = Path(args.output) if args.output else settings.output_dir

    key_rotator = KeyRotator(
        settings.agnes_api_keys,
        cooldown_base_sec=settings.cooldown_base_sec,
        cooldown_max_sec=settings.cooldown_max_sec,
        cooldown_step_sec=settings.cooldown_step_sec,
        cooldown_decay_after_success=settings.cooldown_decay_after_success,
    )
    log.info(
        f"Đã nạp {key_rotator.total_keys} API key | cooldown nền: "
        f"{settings.cooldown_base_sec:.0f}s, tối đa: {settings.cooldown_max_sec:.0f}s "
        f"(tự tăng {settings.cooldown_step_sec:.0f}s/lần lỗi, tự giảm sau "
        f"{settings.cooldown_decay_after_success} lần thành công liên tiếp)"
    )

    async with AgnesClient(key_rotator) as engine:
        runner = PipelineRunner(engine)
        pipeline_input = PipelineInput(
            script_text=script_text,
            style_hint=args.style,
            subject_name=args.subject,
            reference_image_url=args.reference,
            keep_character_consistent=args.keep_character,
            quota_mode=quota_mode,
            max_concurrent_image_requests=settings.max_concurrent_image_requests,
            max_concurrent_video_submit=settings.max_concurrent_video_submit,
            poll_interval_sec=settings.poll_interval_sec,
            output_dir=output_dir,
        )
        result = await runner.run(pipeline_input)

    print("\n=== HOÀN TẤT ===")
    print(f"Video cuối: {result.final_video_path}")
    if result.warnings:
        print("Cảnh báo:")
        for w in result.warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Đã dừng bởi người dùng (Ctrl+C)")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        log.error(f"Lỗi: {e}")
        sys.exit(1)
