"""
server/job_manager.py
------------------------
Quản lý vòng đời 1 lần chạy pipeline (job): tạo job, chạy nền (background
task), và cho phép UI theo dõi log/tiến độ REAL-TIME qua WebSocket.

Cách stream log: mỗi job có 1 asyncio.Queue riêng. Một logging.Handler dùng
contextvars để biết "đang chạy job nào" trên task hiện tại, rồi đẩy từng
dòng log vào đúng queue của job đó — không cần sửa code logging.get_logger()
đang dùng khắp pipeline.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from config import settings
from core.router import QuotaMode
from engines.agnes_client import AgnesClient
from orchestrator.pipeline_runner import PipelineInput, PipelineRunner
from utils.key_rotation import KeyRotator

current_job_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_job_id", default=None)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    result_video_path: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    log_history: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    done_event: asyncio.Event = field(default_factory=asyncio.Event)

    def broadcast(self, line: str) -> None:
        self.log_history.append(line)
        for q in self.subscribers:
            q.put_nowait(line)

    def subscribe(self) -> asyncio.Queue:
        """Tạo queue RIÊNG cho 1 kết nối WS mới — chỉ nhận log phát sinh SAU
        thời điểm subscribe, tránh trùng lặp với log_history đã replay."""
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)


class QueueLogHandler(logging.Handler):
    """1 handler DUY NHẤT gắn vào root logger. Với mỗi log record, tìm job
    đang active trên context hiện tại (qua contextvars) rồi broadcast tới
    mọi WS client đang theo dõi job đó — các job chạy song song không bị lẫn
    log của nhau, và nhiều client cùng xem 1 job không bị trùng dòng."""

    def __init__(self, registry: "JobRegistry"):
        super().__init__()
        self._registry = registry

    def emit(self, record: logging.LogRecord) -> None:
        job_id = current_job_id.get()
        if job_id is None:
            return
        job = self._registry.get(job_id)
        if job is None:
            return
        line = self.format(record)
        job.broadcast(line)


class JobRegistry:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self) -> Job:
        job = Job(id=str(uuid.uuid4())[:8])
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


registry = JobRegistry()

_handler = QueueLogHandler(registry)
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
logging.getLogger().addHandler(_handler)


async def start_job(
    script_text: str,
    style: str,
    subject: str,
    reference_image_url: str | None,
    keep_character: bool,
    quota_mode_raw: str,
) -> Job:
    settings.validate()
    job = registry.create()
    job.status = JobStatus.PENDING

    asyncio.create_task(_run_job(job, script_text, style, subject, reference_image_url, keep_character, quota_mode_raw))
    return job


async def _run_job(
    job: Job,
    script_text: str,
    style: str,
    subject: str,
    reference_image_url: str | None,
    keep_character: bool,
    quota_mode_raw: str,
) -> None:
    token = current_job_id.set(job.id)
    job.status = JobStatus.RUNNING
    try:
        quota_mode = QuotaMode.SAVE if quota_mode_raw == "tiet_kiem" else QuotaMode.NORMAL
        key_rotator = KeyRotator(
            settings.agnes_api_keys,
            cooldown_base_sec=settings.cooldown_base_sec,
            cooldown_max_sec=settings.cooldown_max_sec,
            cooldown_step_sec=settings.cooldown_step_sec,
            cooldown_decay_after_success=settings.cooldown_decay_after_success,
        )
        job_output_dir = settings.output_dir / job.id

        async with AgnesClient(key_rotator) as engine:
            runner = PipelineRunner(engine)
            pipeline_input = PipelineInput(
                script_text=script_text,
                style_hint=style,
                subject_name=subject,
                reference_image_url=reference_image_url or None,
                keep_character_consistent=keep_character,
                quota_mode=quota_mode,
                max_concurrent_image_requests=settings.max_concurrent_image_requests,
                max_concurrent_video_submit=settings.max_concurrent_video_submit,
                poll_interval_sec=settings.poll_interval_sec,
                output_dir=job_output_dir,
            )
            result = await runner.run(pipeline_input)

        job.result_video_path = str(result.final_video_path)
        job.warnings = result.warnings
        job.status = JobStatus.COMPLETED
    except Exception as e:  # noqa: BLE001
        job.error = str(e)
        job.status = JobStatus.FAILED
        job.broadcast(f"[LỖI] {e}")
    finally:
        job.done_event.set()
        current_job_id.reset(token)
