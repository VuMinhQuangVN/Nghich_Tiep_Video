"""
server/job_manager.py
------------------------
Quản lý vòng đời job: tạo, chạy nền, stream log real-time qua WebSocket.

Flow mới (gọn hơn):
  ảnh sản phẩm + goal + platform
    → CreativeDirector (1 lần gọi AI → ra shot list)
    → PipelineRunner (loop: gen ảnh → gen video → ghép)
    → VideoPostProcessor (optional: voiceover, music, subtitles)
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

from config import settings
from core.creative_director import CreativeDirector
from core.subject_lock import SubjectLockBuilder
from models.creative_plan import CreativeInput
from orchestrator.creative_pipeline_adapter import CreativePipelineAdapter
from orchestrator.pipeline_runner import PipelineRunner
from engines.agnes_client import AgnesClient
from engines.generation_facade import GenerationFacade
from engines.video_router import build_video_engine
from utils.key_rotation import KeyRotator
from utils.video_post_processor import VideoPostProcessor

log = logging.getLogger(__name__)

current_job_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_job_id", default=None
)


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
    # Script "brain" is exposed to UI as soon as CreativeDirector finishes.
    creative_plan: dict | None = None
    creative_candidates: list[dict] = field(default_factory=list)
    selected_candidate: int | None = None
    phase: str = "brain"  # brain = chọn kịch bản; render = đang tạo video
    creative_request: dict | None = None
    log_history: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    done_event: asyncio.Event = field(default_factory=asyncio.Event)

    def broadcast(self, line: str) -> None:
        self.log_history.append(line)
        for q in self.subscribers:
            q.put_nowait(line)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)


class GlobalLogHub:
    """Global application logger stream used by /logger."""
    def __init__(self):
        self.history: list[str] = []
        self.subscribers: list[asyncio.Queue] = []
        self.max_history = 2000

    def publish(self, line: str) -> None:
        self.history.append(line)
        if len(self.history) > self.max_history:
            del self.history[:-self.max_history]
        for q in list(self.subscribers):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)


global_logger_hub = GlobalLogHub()


class GlobalQueueLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global_logger_hub.publish(self.format(record))


_global_logger_handler = GlobalQueueLogHandler()
_global_logger_handler.setFormatter(
    logging.Formatter("%(asctime)s  %(levelname)s  %(name)s  %(message)s", datefmt="%H:%M:%S")
)
_root_logger = logging.getLogger()
# Python's default root level is WARNING, which drops the INFO records
# emitted by the creative pipeline before our queue handlers can see them.
_root_logger.setLevel(logging.INFO)
_root_logger.addHandler(_global_logger_handler)


class QueueLogHandler(logging.Handler):
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
        job.broadcast(self.format(record))


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
_root_logger.addHandler(_handler)


def _make_key_rotator() -> KeyRotator:
    return KeyRotator(
        settings.agnes_api_keys,
        cooldown_base_sec=settings.cooldown_base_sec,
        cooldown_max_sec=settings.cooldown_max_sec,
        cooldown_step_sec=settings.cooldown_step_sec,
        cooldown_decay_after_success=settings.cooldown_decay_after_success,
    )


# ─── Creative job (flow mới) ────────────────────────────────────────────────

async def start_creative_job(
    product_reference_urls: list[str],
    style_reference_urls: list[str],
    goal: str,
    platform: str,
    duration_sec: float,
    language: str = "vi",
    voiceover_path: str | None = None,
    background_music_path: str | None = None,
    subtitles_path: str | None = None,
    video_engine: str = "auto",
    style: str = "Auto",
    aspect_ratio: str = "9:16",
) -> Job:
    settings.validate()

    references = [x.strip() for x in product_reference_urls if isinstance(x, str) and x.strip()]
    if not references:
        raise ValueError("Cần ít nhất một URL/ảnh sản phẩm")
    if not goal.strip():
        raise ValueError("goal không được rỗng")
    if not platform.strip():
        raise ValueError("platform không được rỗng")
    if duration_sec <= 0:
        raise ValueError("duration_sec phải > 0")

    job = registry.create()
    job.status = JobStatus.PENDING
    asyncio.create_task(_run_creative_job(
        job=job,
        product_reference_urls=references,
        style_reference_urls=list(style_reference_urls),
        goal=goal,
        platform=platform,
        duration_sec=duration_sec,
        language=language,
        voiceover_path=voiceover_path,
        background_music_path=background_music_path,
        subtitles_path=subtitles_path,
        video_engine=video_engine,
        style=style,
        aspect_ratio=aspect_ratio,
    ))
    return job


async def start_creative_plan_job(**kwargs) -> Job:
    """Create 5 creative candidates only; production starts after selection."""
    settings.validate()
    refs = [x.strip() for x in kwargs["product_reference_urls"] if isinstance(x, str) and x.strip()]
    if not refs:
        raise ValueError("Cần ít nhất một URL/ảnh sản phẩm")
    if not kwargs["goal"].strip() or not kwargs["platform"].strip():
        raise ValueError("goal và platform không được rỗng")
    if float(kwargs["duration_sec"]) <= 0:
        raise ValueError("duration_sec phải > 0")
    job = registry.create()
    job.creative_request = dict(kwargs)
    asyncio.create_task(_run_creative_plan_job(job, **kwargs))
    return job


async def _run_creative_plan_job(job: Job, **kwargs) -> None:
    token = current_job_id.set(job.id)
    job.status = JobStatus.RUNNING
    try:
        async with AgnesClient(_make_key_rotator()) as client:
            engine = GenerationFacade(client, build_video_engine(client, kwargs.get("video_engine", "auto")))
            creative_input = CreativeInput(
                product_reference_urls=kwargs["product_reference_urls"],
                style_reference_urls=kwargs.get("style_reference_urls", []),
                goal=kwargs["goal"].strip(), platform=kwargs["platform"].strip(),
                duration_sec=float(kwargs["duration_sec"]), language=kwargs.get("language", "vi").strip() or "vi",
                style=kwargs.get("style", "Auto"), aspect_ratio=kwargs.get("aspect_ratio", "9:16"),
            )
            candidates = await CreativeDirector(engine).brainstorm(creative_input)
        job.creative_candidates = [_creative_plan_to_dict(plan) for plan in candidates]
        job.creative_plan = job.creative_candidates[0] if job.creative_candidates else None
        log.info("Creative Brain: có %d phương án. Chờ người dùng chọn trước khi render.", len(job.creative_candidates))
        job.status = JobStatus.COMPLETED
    except Exception as e:
        job.error = str(e); job.status = JobStatus.FAILED
        job.broadcast(f"[LỖI] {e}")
        log.exception("Brain job %s thất bại", job.id)
    finally:
        job.done_event.set(); current_job_id.reset(token)


async def generate_selected_candidate(job_id: str, candidate_index: int) -> Job:
    job = registry.get(job_id)
    if job is None: raise ValueError("job không tồn tại")
    if not job.creative_candidates: raise ValueError("Job chưa có 5 kịch bản")
    if candidate_index < 0 or candidate_index >= len(job.creative_candidates): raise ValueError("candidate_index không hợp lệ")
    job.selected_candidate = candidate_index
    job.creative_plan = job.creative_candidates[candidate_index]
    job.phase = "render"
    job.status = JobStatus.RUNNING
    job.error = None; job.done_event = asyncio.Event()
    asyncio.create_task(_run_selected_candidate(job))
    return job


async def _run_selected_candidate(job: Job) -> None:
    req = job.creative_request or {}
    token = current_job_id.set(job.id)
    try:
        plan_dict = job.creative_candidates[job.selected_candidate or 0]
        # Rebuild a CreativePlan from the selected JSON so the existing pipeline stays unchanged.
        from models.creative_plan import CreativePlan, ShotPlan
        plan = CreativePlan(
            title=plan_dict["title"], direction=plan_dict["direction"], style_suggestion=plan_dict["styleSuggestion"],
            common_visual_context=plan_dict["commonVisualContext"], aspect_ratio=plan_dict["aspectRatio"],
            total_duration=float(plan_dict["totalDuration"]),
            shots=[ShotPlan(index=int(x["id"]), description=x["description"], visual_prompt=x["visualPrompt"],
                            voiceover=x.get("voiceover", ""), duration=float(x["duration"]),
                            common_visual_context=plan_dict["commonVisualContext"]) for x in plan_dict["shots"]],
        )
        await _produce_from_plan(job, plan, req)
    except Exception as e:
        job.error = str(e); job.status = JobStatus.FAILED
        job.broadcast(f"[LỖI] {e}"); log.exception("Render job %s thất bại", job.id)
    finally:
        job.done_event.set(); current_job_id.reset(token)


async def _produce_from_plan(job: Job, creative_plan, req: dict) -> None:
    job_output_dir = settings.output_dir / job.id
    async with AgnesClient(_make_key_rotator()) as client:
        engine = GenerationFacade(client, build_video_engine(client, req.get("video_engine", "auto")))
        subject_lock = SubjectLockBuilder().build(
            product_reference_urls=req["product_reference_urls"], style_reference_urls=req.get("style_reference_urls", []))
        pipeline_input = CreativePipelineAdapter.to_pipeline_input(
            creative_plan=creative_plan, subject_lock=subject_lock, output_dir=job_output_dir,
            max_concurrent_image_requests=settings.max_concurrent_image_requests,
            max_concurrent_video_submit=settings.max_concurrent_video_submit, poll_interval_sec=settings.poll_interval_sec)
        result = await PipelineRunner(engine).run(pipeline_input)
    postprocessed_path = job_output_dir / "final_video_postprocessed.mp4"
    post_options = CreativePipelineAdapter.to_post_process_options(
        creative_plan, voiceover_path=Path(req["voiceover_path"]) if req.get("voiceover_path") else None,
        background_music_path=Path(req["background_music_path"]) if req.get("background_music_path") else None,
        subtitles_path=Path(req["subtitles_path"]) if req.get("subtitles_path") else None)
    final_video = await VideoPostProcessor().process(result.final_video_path, postprocessed_path, post_options)
    job.result_video_path = str(final_video); job.warnings = result.warnings; job.status = JobStatus.COMPLETED
    log.info("Job render hoàn tất: %s", final_video)
def _creative_plan_to_dict(plan) -> dict:
    """Serialize the creative brain result for the UI/API."""
    return {
        "title": plan.title,
        "direction": plan.direction,
        "styleSuggestion": plan.style_suggestion,
        "commonVisualContext": plan.common_visual_context,
        "aspectRatio": plan.aspect_ratio,
        "totalDuration": plan.total_duration,
        "shots": [
            {
                "id": shot.index,
                "description": shot.description,
                "visualPrompt": shot.visual_prompt,
                "voiceover": shot.voiceover,
                "duration": shot.duration,
            }
            for shot in plan.shots
        ],
    }


async def _run_creative_job(
    job: Job,
    product_reference_urls: list[str],
    style_reference_urls: list[str],
    goal: str,
    platform: str,
    duration_sec: float,
    language: str,
    voiceover_path: str | None = None,
    background_music_path: str | None = None,
    subtitles_path: str | None = None,
    video_engine: str = "auto",
    style: str = "Auto",
    aspect_ratio: str = "9:16",
) -> None:
    token = current_job_id.set(job.id)
    job.status = JobStatus.RUNNING
    try:
        job_output_dir = settings.output_dir / job.id

        async with AgnesClient(_make_key_rotator()) as client:
            engine = GenerationFacade(client, build_video_engine(client, video_engine))

            creative_input = CreativeInput(
                product_reference_urls=product_reference_urls,
                style_reference_urls=style_reference_urls,
                goal=goal.strip(),
                platform=platform.strip(),
                duration_sec=float(duration_sec),
                language=language.strip() or "vi",
                style=style,
                aspect_ratio=aspect_ratio,
            )

            # Bước 1: AI phân tích sản phẩm + lên kịch bản (1 lần gọi duy nhất)
            log.info("Đang phân tích sản phẩm và lên kịch bản...")
            creative_plan = await CreativeDirector(engine).direct(creative_input)
            job.creative_plan = _creative_plan_to_dict(creative_plan)
            log.info(
                "Kịch bản: '%s' — %d cảnh, tổng %.1fs",
                creative_plan.title, len(creative_plan.shots), creative_plan.total_duration,
            )

            # Bước 2: Tạo SubjectLock (reference images)
            subject_lock = SubjectLockBuilder().build(
                product_reference_urls=product_reference_urls,
                style_reference_urls=style_reference_urls,
            )

            # Bước 3: Chạy pipeline gen ảnh → gen video → ghép
            pipeline_input = CreativePipelineAdapter.to_pipeline_input(
                creative_plan=creative_plan,
                subject_lock=subject_lock,
                output_dir=job_output_dir,
                max_concurrent_image_requests=settings.max_concurrent_image_requests,
                max_concurrent_video_submit=settings.max_concurrent_video_submit,
                poll_interval_sec=settings.poll_interval_sec,
            )
            result = await PipelineRunner(engine).run(pipeline_input)

        # Bước 4: Post-processing (voiceover, music, subtitles)
        postprocessed_path = job_output_dir / "final_video_postprocessed.mp4"
        post_options = CreativePipelineAdapter.to_post_process_options(
            creative_plan,
            voiceover_path=Path(voiceover_path) if voiceover_path else None,
            background_music_path=Path(background_music_path) if background_music_path else None,
            subtitles_path=Path(subtitles_path) if subtitles_path else None,
        )
        final_video = await VideoPostProcessor().process(
            result.final_video_path, postprocessed_path, post_options
        )
        job.result_video_path = str(final_video)
        job.warnings = result.warnings
        job.status = JobStatus.COMPLETED
        log.info("Job hoàn tất: %s", final_video)

    except Exception as e:
        job.error = str(e)
        job.status = JobStatus.FAILED
        job.broadcast(f"[LỖI] {e}")
        log.exception("Job %s thất bại", job.id)
    finally:
        job.done_event.set()
        current_job_id.reset(token)


# ─── Script job (mode thủ công cũ, giữ lại) ────────────────────────────────

async def start_job(
    script_text: str,
    style: str,
    subject: str,
    reference_image_url: str | None,
    keep_character: bool,
    video_engine: str = "auto",
) -> Job:
    settings.validate()
    job = registry.create()
    job.status = JobStatus.PENDING
    asyncio.create_task(_run_script_job(
        job, script_text, style, subject,
        reference_image_url, keep_character, video_engine,
    ))
    return job


async def _run_script_job(
    job: Job,
    script_text: str,
    style: str,
    subject: str,
    reference_image_url: str | None,
    keep_character: bool,
    video_engine: str = "auto",
) -> None:
    token = current_job_id.set(job.id)
    job.status = JobStatus.RUNNING
    try:
        job.broadcast("[Script mode] Tính năng script thủ công đang được chuyển sang Creative Mode.")
        job.broadcast("Vui lòng dùng /api/creative-jobs với ảnh sản phẩm.")
        job.status = JobStatus.FAILED
        job.error = "Script mode không còn hỗ trợ. Dùng Creative Mode."
    finally:
        job.done_event.set()
        current_job_id.reset(token)
