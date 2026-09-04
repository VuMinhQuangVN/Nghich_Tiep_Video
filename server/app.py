"""
server/app.py
----------------
FastAPI app cho UI local. Chạy bằng: `python app.py` (ở thư mục gốc project).

Route chính:
  GET  /                          -> giao diện web (static/index.html)
  POST /api/jobs                  -> tạo job mới, chạy pipeline nền, trả job_id
  WS   /ws/jobs/{job_id}          -> stream log real-time cho 1 job
  GET  /api/jobs/{job_id}         -> trạng thái + kết quả hiện tại của job
  GET  /output/{job_id}/{file}    -> tải/xem video kết quả
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from server.job_manager import JobStatus, registry, start_job

ROOT_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="AI Video Content Tool")


@app.get("/")
async def index():
    return FileResponse(ROOT_DIR / "static" / "index.html")


@app.post("/api/jobs")
async def create_job(
    script_text: str = Form(...),
    style: str = Form(""),
    subject: str = Form(""),
    reference_image_url: str = Form(""),
    keep_character: bool = Form(False),
    quota_mode: str = Form("tiet_kiem"),
):
    job = await start_job(
        script_text=script_text,
        style=style or "cinematic, natural lighting, photographic",
        subject=subject or "chủ thể chính",
        reference_image_url=reference_image_url.strip() or None,
        keep_character=keep_character,
        quota_mode_raw=quota_mode,
    )
    return {"job_id": job.id}


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
    })


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
