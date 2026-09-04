"""
orchestrator/task_queue.py
-----------------------------
Chạy N coroutine song song nhưng giới hạn concurrency bằng semaphore, đúng
thiết kế mục 3 (software-design.md): sinh ảnh tối đa 3-5 luồng, submit video
tối đa 2-3 luồng. Lỗi 1 task KHÔNG chặn task khác (mỗi ảnh độc lập).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def run_bounded(
    coros: list[Callable[[], Awaitable[T]]],
    max_concurrency: int,
) -> list[T | Exception]:
    """Chạy danh sách hàm async song song, giới hạn concurrency.
    Trả về list kết quả theo ĐÚNG thứ tự đầu vào; phần tử lỗi trả về
    Exception thay vì raise ngay, để lỗi 1 task không làm hỏng các task khác.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _wrapped(coro_factory: Callable[[], Awaitable[T]]) -> T | Exception:
        async with semaphore:
            try:
                return await coro_factory()
            except Exception as e:  # noqa: BLE001 - cố ý bắt hết để không chặn task khác
                return e

    return await asyncio.gather(*[_wrapped(c) for c in coros])
