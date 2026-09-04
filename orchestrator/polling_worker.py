"""
orchestrator/polling_worker.py
----------------------------------
Poll trạng thái nhiều video_id cùng lúc theo pattern task-queue + polling
worker (mục 3, software-design.md): 1 vòng lặp nền, mỗi ~poll_interval_sec
giây poll TẤT CẢ video_id đang queued/in_progress, KHÔNG mở 1 luồng poll
riêng cho từng video.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from engines.base_engine import BaseEngine, VideoStatus, VideoTaskHandle
from utils.logger import get_logger

log = get_logger(__name__)


async def poll_until_done(
    engine: BaseEngine,
    video_ids: list[str],
    poll_interval_sec: float = 4.0,
    max_wait_sec: float = 900.0,
    on_update: Callable[[str, VideoTaskHandle], None] | None = None,
) -> dict[str, VideoTaskHandle]:
    """Poll tất cả video_id cho tới khi tất cả completed/failed hoặc hết
    max_wait_sec. Trả về dict video_id -> VideoTaskHandle cuối cùng."""
    pending = set(video_ids)
    results: dict[str, VideoTaskHandle] = {}
    elapsed = 0.0

    while pending and elapsed < max_wait_sec:
        handles = await asyncio.gather(
            *[engine.poll_video_task(vid) for vid in pending],
            return_exceptions=True,
        )
        for vid, handle in zip(list(pending), handles):
            if isinstance(handle, Exception):
                log.warning(f"Poll {vid} lỗi tạm thời: {handle}")
                continue
            results[vid] = handle
            if on_update:
                on_update(vid, handle)
            if handle.status in (VideoStatus.COMPLETED, VideoStatus.FAILED):
                pending.discard(vid)
                status_label = "✓ xong" if handle.status == VideoStatus.COMPLETED else "✗ lỗi"
                log.info(f"Video {vid}: {status_label}")

        if pending:
            await asyncio.sleep(poll_interval_sec)
            elapsed += poll_interval_sec

    for vid in pending:
        log.warning(f"Video {vid} vượt quá thời gian chờ tối đa ({max_wait_sec}s), đánh dấu lỗi")
        results[vid] = VideoTaskHandle(video_id=vid, status=VideoStatus.FAILED, error="timeout")

    return results
