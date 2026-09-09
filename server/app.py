"""
server/app.py
----------------
FastAPI app cho UI local. Chạy bằng: `python app.py` (ở thư mục gốc project).

Route chính:
  GET  /                          -> giao diện web (static/index.html)
  POST /api/creative-plans        -> Creative Brain tạo 5 candidate
  POST /api/creative-plans/{id}/generate -> render candidate đã chọn
  GET  /api/jobs/{job_id}         -> trạng thái + kết quả hiện tại của job
  WS   /ws/jobs/{job_id}          -> stream log real-time cho job
  GET  /logger                    -> logger toàn hệ thống
  WS   /ws/logger                 -> stream logger toàn hệ thống
  GET  /output/{job_id}/{file}    -> tải/xem video kết quả
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from server.job_manager import JobStatus, registry, start_creative_plan_job, generate_selected_candidate, global_logger_hub
from utils.image_reference import upload_to_data_uri

ROOT_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="AI Video Content Tool")


def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Ignore benign Windows socket-reset noise from clients closing connections."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054:
        return
    loop.default_exception_handler(context)


@app.on_event("startup")
async def configure_asyncio_exception_handler() -> None:
    asyncio.get_running_loop().set_exception_handler(_asyncio_exception_handler)


@app.get("/")
async def index():
    return FileResponse(
        ROOT_DIR / "static" / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.post("/api/creative-plans")
async def create_creative_plans(
    product_reference_url: str = Form(""), product_reference_urls: str = Form(""),
    product_image: UploadFile | None = File(None), product_images: list[UploadFile] | None = File(None),
    style_reference_urls: str = Form(""), style_images: list[UploadFile] | None = File(None),
    goal: str = Form(...), platform: str = Form(...), duration_sec: float = Form(30), language: str = Form("vi"),
    voiceover_path: str = Form(""), background_music_path: str = Form(""),
    subtitles_path: str = Form(""), video_engine: str = Form("auto"), style: str = Form("Auto"), aspect_ratio: str = Form("9:16"),
):
    try:
        references = []
        raw_urls = product_reference_urls.strip() or product_reference_url.strip()
        if raw_urls:
            references.extend(x.strip() for x in raw_urls.replace("\r", "").replace(",", "\n").split("\n") if x.strip())
        uploads = [x for x in ([product_image] if product_image is not None else []) if x and x.filename]
        uploads.extend(x for x in (product_images or []) if x and x.filename)
        for image in uploads: references.append(await upload_to_data_uri(image))
        style_refs = []
        if style_reference_urls.strip():
            style_refs.extend(x.strip() for x in style_reference_urls.replace("\r", "").replace(",", "\n").split("\n") if x.strip())
        for image in (style_images or []):
            if image and image.filename: style_refs.append(await upload_to_data_uri(image))
        if not references: raise ValueError("Cần ít nhất một URL ảnh sản phẩm hoặc upload ảnh sản phẩm")
        job = await start_creative_plan_job(
            product_reference_urls=references, style_reference_urls=style_refs, goal=goal, platform=platform,
            duration_sec=duration_sec, language=language,
            voiceover_path=voiceover_path.strip() or None, background_music_path=background_music_path.strip() or None,
            subtitles_path=subtitles_path.strip() or None, video_engine=video_engine.strip() or "auto",
            style=style.strip() or "Auto", aspect_ratio=aspect_ratio.strip() or "9:16")
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"job_id": job.id}


@app.post("/api/creative-plans/{job_id}/generate")
async def generate_creative_plan(job_id: str, candidate_index: int = Form(...)):
    try:
        job = await generate_selected_candidate(job_id, candidate_index)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"job_id": job.id, "candidate_index": candidate_index}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = registry.get(job_id)
    if job is None:
        return JSONResponse({"error": "job không tồn tại"}, status_code=404)
    video_url = None
    if job.result_video_path:
        p = Path(job.result_video_path)
        video_url = f"/output/{job_id}/{p.name}"
    return {
        "id": job.id,
        "status": job.status.value,
        "error": job.error,
        "warnings": job.warnings,
        "creative_plan": job.creative_plan,
        "creative_candidates": job.creative_candidates,
        "selected_candidate": job.selected_candidate,
        "video_url": video_url,
        "log_history": job.log_history,
    }


@app.websocket("/ws/jobs/{job_id}")
async def job_logs_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = registry.get(job_id)
    if job is None:
        await websocket.send_json({"type": "error", "message": "job không tồn tại"})
        await websocket.close()
        return

    # replay log đã có (nếu client kết nối sau khi job đã bắt đầu chạy)
    for line in job.log_history:
        await websocket.send_json({"type": "log", "line": line})

    # nếu job đã xong TRƯỚC khi client kịp subscribe, trả kết quả luôn
    if job.done_event.is_set():
        await _send_done(websocket, job)
        return

    queue = job.subscribe()
    try:
        while True:
            get_line = asyncio.create_task(queue.get())
            wait_done = asyncio.create_task(job.done_event.wait())
            done, pending = await asyncio.wait(
                {get_line, wait_done}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

            if get_line in done:
                await websocket.send_json({"type": "log", "line": get_line.result()})
            if wait_done in done:
                # đợi nốt log còn trong queue rồi mới báo done, tránh mất dòng cuối
                while not queue.empty():
                    await websocket.send_json({"type": "log", "line": queue.get_nowait()})
                await _send_done(websocket, job)
                break
    except WebSocketDisconnect:
        pass
    finally:
        job.unsubscribe(queue)


async def _send_done(websocket: WebSocket, job) -> None:
    video_url = None
    if job.result_video_path:
        video_url = f"/output/{job.id}/{Path(job.result_video_path).name}"
    await websocket.send_json({
        "type": "done",
        "status": job.status.value,
        "error": job.error,
        "warnings": job.warnings,
        "video_url": video_url,
        "phase": getattr(job, "phase", "render"),
    })



@app.get("/logger")
async def logger_page():
    return FileResponse(ROOT_DIR / "static" / "logger.html")


@app.websocket("/ws/logger")
async def logger_ws(websocket: WebSocket):
    await websocket.accept()
    hub = global_logger_hub
    for line in hub.history:
        await websocket.send_json({"type": "log", "line": line})
    queue = hub.subscribe()
    try:
        while True:
            line = await queue.get()
            await websocket.send_json({"type": "log", "line": line})
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(queue)


@app.get("/output/{job_id}/{filename}")
async def get_output_file(job_id: str, filename: str):
    path = settings.output_dir / job_id / filename
    if not path.exists():
        return JSONResponse({"error": "không tìm thấy file"}, status_code=404)
    return FileResponse(path)


app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")


if __name__ == "__main__":
    import uvicorn

    settings.validate()
    print("\n  AI Video Content Tool đang chạy tại: http://127.0.0.1:8420\n")
    uvicorn.run(app, host="127.0.0.1", port=8420)
