#!/usr/bin/env python3
"""
AI Video Content Tool — single-file local app
================================================
Kiến trúc: Clean Architecture (Domain -> Application -> Infrastructure -> Presentation)
Nguyên tắc SOLID áp dụng:
  S (Single Responsibility) — mỗi class chỉ làm đúng 1 việc (VisionAnalyzer chỉ phân
      tích ảnh, ImageEngine chỉ sinh ảnh, VideoEngine chỉ sinh video, Router chỉ quyết
      định technique...)
  O (Open/Closed)          — thêm engine mới (Omni Flash sau này) chỉ cần viết thêm 1
      class implement đúng Protocol, không sửa code Orchestrator/Router hiện có.
  L (Liskov Substitution)  — mọi implementation của ImageEnginePort/VideoEnginePort có
      thể thay thế nhau mà không phá vỡ Orchestrator (cùng tuân theo 1 interface).
  I (Interface Segregation)— tách riêng VisionAnalyzerPort / ImageEnginePort /
      VideoEnginePort thay vì gộp 1 "EnginePort" khổng lồ — implementation nào không
      cần vision thì không phải implement nó.
  D (Dependency Inversion) — Orchestrator (use case) chỉ phụ thuộc vào các Protocol
      (abstraction) trong Application layer, không phụ thuộc trực tiếp vào AgnesClient
      (chi tiết implementation) — muốn đổi provider chỉ cần đổi lúc "wiring" ở main().

Cách chạy:
    pip install flask requests --break-system-packages
    export AGNES_API_KEY="your_api_key_here"
    python3 ai_video_tool.py
    Mở trình duyệt: http://127.0.0.1:5000

Ghi chú tri thức (rút gọn từ Knowledge Base — xem thêm bộ file .md đã cung cấp):
  - Router chọn technique dựa trên: số scene, engine có hỗ trợ keyframe_array
    không, quota_mode (tiết kiệm / bình thường).
  - Character Lock luôn chạy trước nếu có nhân vật lặp lại — sinh 1 ảnh nhiều góc,
    dùng làm ảnh tham chiếu xuyên suốt toàn bộ scene.
  - Agnes AI hiện có 3 model riêng: agnes-2.5-flash (LLM+vision), agnes-image-2.1-flash
    (tạo ảnh), agnes-video-v2.0 (tạo video, async, hỗ trợ mode "keyframes").
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol, runtime_checkable

import requests

from config import settings
from flask import Flask, jsonify, request


# ════════════════════════════════════════════════════════════════════════
# 1. DOMAIN LAYER — entities & value objects thuần, không phụ thuộc gì bên ngoài
# ════════════════════════════════════════════════════════════════════════

class QuotaMode(str, enum.Enum):
    SAVE = "tiết_kiệm"
    NORMAL = "bình_thường"


class Technique(str, enum.Enum):
    SINGLE_SHOT_DIRECT = "single_shot_direct"
    FRAME_TO_FRAME_CHAIN = "frame_to_frame_chain"
    KEYFRAME_ARRAY = "keyframe_array"
    STORYBOARD_SHEET = "storyboard_sheet"
    SCENE_EXTEND_EDIT = "scene_extend_edit"


@dataclasses.dataclass
class Scene:
    """1 đơn vị kịch bản nhỏ nhất — tương ứng 1 'cảnh' trong video."""
    index: int
    description: str
    camera_move: str
    duration_sec: int
    image_url: str | None = None
    video_url: str | None = None
    video_task_id: str | None = None
    status: str = "planned"  # planned -> image_ready -> queued -> in_progress -> completed -> failed


@dataclasses.dataclass
class Project:
    """Toàn bộ 1 lần chạy pipeline — từ input tới video cuối."""
    id: str
    script_text: str
    reference_image_urls: list[str]
    keep_character_consistent: bool
    quota_mode: QuotaMode
    scenes: list[Scene] = dataclasses.field(default_factory=list)
    character_sheet_url: str | None = None
    chosen_technique: Technique | None = None
    final_video_url: str | None = None


# ════════════════════════════════════════════════════════════════════════
# 2. APPLICATION LAYER — Ports (interfaces) mà Orchestrator phụ thuộc vào.
#    Đây là ranh giới SOLID quan trọng nhất: Orchestrator KHÔNG biết Agnes là gì,
#    chỉ biết "1 thứ gì đó implement đúng Protocol này".
# ════════════════════════════════════════════════════════════════════════

@runtime_checkable
class VisionAnalyzerPort(Protocol):
    def analyze_reference_image(self, image_url: str) -> str:
        """Trả về mô tả văn bản: chủ thể, phong cách, ánh sáng... trích từ ảnh."""
        ...

    def plan_scenes(self, script_text: str, style_hint: str) -> list[Scene]:
        """Chia kịch bản thành danh sách Scene có mô tả + camera move + thời lượng."""
        ...


@runtime_checkable
class ImageEnginePort(Protocol):
    def generate_image(self, prompt: str, reference_image_url: str | None = None) -> str:
        """Sinh 1 ảnh, trả về URL. reference_image_url dùng cho image-to-image."""
        ...


@runtime_checkable
class VideoEnginePort(Protocol):
    """Interface Segregation: engine không hỗ trợ keyframe/edit vẫn hợp lệ,
    chỉ cần raise NotImplementedError đúng chỗ — Router sẽ không route vào đó
    nhờ capabilities() khai báo trung thực."""

    def capabilities(self) -> dict:
        """VD: {'supports_keyframe_array': True, 'supports_edit': False, ...}"""
        ...

    def submit_single_image_video(self, prompt: str, image_url: str, duration_sec: int) -> str:
        """Trả về task_id (async)."""
        ...

    def submit_keyframe_video(self, prompt: str, keyframe_urls: list[str], duration_sec: int) -> str:
        ...

    def poll_task(self, task_id: str) -> dict:
        """Trả về {'status': 'queued'|'in_progress'|'completed'|'failed', 'url': str|None}"""
        ...


# ════════════════════════════════════════════════════════════════════════
# 3. INFRASTRUCTURE LAYER — implementation cụ thể cho Agnes AI.
#    Đây là nơi DUY NHẤT trong file này "biết" về HTTP/API key/JSON của Agnes.
# ════════════════════════════════════════════════════════════════════════

AGNES_BASE_URL = settings.agnes_base_url


class AgnesHttpClient:
    """Wrapper HTTP thuần, dùng chung cho mọi lớp Agnes bên dưới (SRP: chỉ lo phần
    gửi request + xử lý lỗi HTTP, không biết gì về prompt hay domain)."""

    def __init__(self, api_key: str, base_url: str = AGNES_BASE_URL, timeout: int = 120):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def post(self, path: str, payload: dict) -> dict:
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(),
                              json=payload, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"Agnes API lỗi {resp.status_code} tại {path}: {resp.text[:500]}")
        return resp.json()

    def get(self, path: str, params: dict) -> dict:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(),
                             params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"Agnes API lỗi {resp.status_code} tại {path}: {resp.text[:500]}")
        return resp.json()


class AgnesVisionAnalyzer:
    """Implement VisionAnalyzerPort bằng model agnes-2.5-flash (LLM + vision)."""

    MODEL = settings.agnes_models.text

    def __init__(self, client: AgnesHttpClient):
        self.client = client

    def analyze_reference_image(self, image_url: str) -> str:
        payload = {
            "model": self.MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Analyze this reference image for use in an AI video pipeline. "
                        "Describe in concise English: subject appearance, outfit/material, "
                        "color palette, lighting mood, and visual style (photographic/3D/anime/etc). "
                        "Output as one dense paragraph, no headers."
                    )},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }],
            "temperature": 0.3,
        }
        data = self.client.post(settings.agnes_endpoints.chat_completions, payload)
        return data["choices"][0]["message"]["content"].strip()

    def plan_scenes(self, script_text: str, style_hint: str) -> list[Scene]:
        system_prompt = (
            "You are a film director AI. Break the user's script into a JSON array of scenes. "
            "Each scene object must have exactly these keys: "
            '"description" (string, subject+action+setting), '
            '"camera_move" (string, short e.g. "slow pan left"), '
            '"duration_sec" (integer, 3-10). '
            "Return ONLY a raw JSON array, no markdown fences, no prose."
        )
        user_prompt = f"Style context: {style_hint}\n\nScript:\n{script_text}"
        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
        }
        data = self.client.post(settings.agnes_endpoints.chat_completions, payload)
        raw = data["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Không parse được JSON scene plan từ LLM: {e}\nRaw: {raw[:300]}")
        scenes = []
        for i, item in enumerate(items, start=1):
            scenes.append(Scene(
                index=i,
                description=item["description"],
                camera_move=item.get("camera_move", ""),
                duration_sec=int(item.get("duration_sec", 5)),
            ))
        return scenes


class AgnesImageEngine:
    """Implement ImageEnginePort bằng model agnes-image-2.1-flash."""

    MODEL = settings.agnes_models.image

    def __init__(self, client: AgnesHttpClient):
        self.client = client

    def generate_image(self, prompt: str, reference_image_url: str | None = None) -> str:
        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "size": "2K",
            "ratio": "16:9",
            "extra_body": {"response_format": "url"},
        }
        if reference_image_url:
            payload["extra_body"]["image"] = [reference_image_url]
        data = self.client.post(settings.agnes_endpoints.image_generations, payload)
        return data["data"][0]["url"]


class AgnesVideoEngine:
    """Implement VideoEnginePort bằng model agnes-video-v2.0 (async task API)."""

    MODEL = settings.agnes_models.video

    def __init__(self, client: AgnesHttpClient):
        self.client = client

    def capabilities(self) -> dict:
        return {
            "supports_storyboard_read": False,
            "supports_keyframe_array": True,
            "supports_edit": False,
            "max_clip_duration_sec": 18,
        }

    @staticmethod
    def _frames_for_duration(duration_sec: int, frame_rate: int = 24) -> int:
        # num_frames phải theo luật 8n+1 và <= 441
        raw = duration_sec * frame_rate
        n = max(1, round((raw - 1) / 8))
        frames = min(441, 8 * n + 1)
        return frames

    def submit_single_image_video(self, prompt: str, image_url: str, duration_sec: int) -> str:
        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "image": image_url,
            "num_frames": self._frames_for_duration(duration_sec),
            "frame_rate": 24,
        }
        data = self.client.post(settings.agnes_endpoints.video_submit, payload)
        return data["video_id"]

    def submit_keyframe_video(self, prompt: str, keyframe_urls: list[str], duration_sec: int) -> str:
        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "extra_body": {"image": keyframe_urls, "mode": "keyframes"},
            "num_frames": self._frames_for_duration(duration_sec),
            "frame_rate": 24,
        }
        data = self.client.post(settings.agnes_endpoints.video_submit, payload)
        return data["video_id"]

    def poll_task(self, task_id: str) -> dict:
        data = self.client.get("/agnesapi", {"video_id": task_id})
        status = data.get("status", "queued")
        url = None
        if status == "completed":
            url = data.get("metadata", {}).get("url")
        return {"status": status, "url": url, "raw": data}


# ════════════════════════════════════════════════════════════════════════
# 4. APPLICATION LAYER — Use cases: Router + PromptComposer + Orchestrator.
#    Đây là "não" của tool, được build lại nguyên vẹn từ Knowledge Base đã thống
#    nhất (router.md, techniques/*.md, character-lock.md).
# ════════════════════════════════════════════════════════════════════════

class TechniqueRouter:
    """SRP: chỉ quyết định technique nào dùng, không biết gì về HTTP/prompt cụ thể."""

    @staticmethod
    def choose(scene_count: int, quota_mode: QuotaMode, engine_caps: dict) -> Technique:
        if scene_count <= 1:
            return Technique.SINGLE_SHOT_DIRECT
        if engine_caps.get("supports_storyboard_read"):
            return Technique.STORYBOARD_SHEET if quota_mode == QuotaMode.SAVE else Technique.FRAME_TO_FRAME_CHAIN
        if engine_caps.get("supports_keyframe_array"):
            return Technique.KEYFRAME_ARRAY if quota_mode == QuotaMode.SAVE else Technique.FRAME_TO_FRAME_CHAIN
        return Technique.FRAME_TO_FRAME_CHAIN


class PromptComposer:
    """SRP: chỉ ghép chuỗi prompt cuối cùng từ dữ liệu đã có, không gọi API nào cả."""

    @staticmethod
    def character_sheet_prompt(style_hint: str) -> str:
        return (
            "Character reference sheet, 4 turnaround angles: front view, 3/4 left, "
            "3/4 right, back view, plus one close-up on face/key detail. "
            f"Subject and style: {style_hint}. Consistent lighting, neutral background, "
            "same subject across all angles, high detail, production-ready reference sheet."
        )

    @staticmethod
    def scene_image_prompt(scene: Scene, style_hint: str) -> str:
        return (
            f"{scene.description}. Camera: {scene.camera_move}. "
            f"Style: {style_hint}. Subject consistent with reference image if provided. "
            "Cinematic lighting, high detail."
        )

    @staticmethod
    def scene_video_prompt(scene: Scene, style_hint: str) -> str:
        return (
            f"{scene.description}. Camera movement: {scene.camera_move}. "
            f"Duration approximately {scene.duration_sec}s. Style: {style_hint}. "
            "Maintain exact subject appearance and style from the reference image."
        )

    @staticmethod
    def keyframe_sequence_prompt(scenes: list[Scene], style_hint: str) -> str:
        beats = "; then ".join(s.description for s in scenes)
        return (
            f"Generate a smooth cinematic transition through these keyframes in order: {beats}. "
            f"Style: {style_hint}. Maintain consistent subject identity, camera logic, "
            "and natural motion between each keyframe."
        )


class Orchestrator:
    """Use case chính — điều phối toàn bộ pipeline.
    Dependency Inversion: constructor chỉ nhận Port (abstraction), KHÔNG import
    AgnesXxx trực tiếp ở đây. Muốn đổi sang Omni Flash sau này, chỉ cần "wiring"
    lại ở main(), class này không đổi 1 dòng nào."""

    def __init__(
        self,
        vision: VisionAnalyzerPort,
        image_engine: ImageEnginePort,
        video_engine: VideoEnginePort,
        router: TechniqueRouter,
        composer: PromptComposer,
        max_parallel_images: int = 4,
    ):
        self.vision = vision
        self.image_engine = image_engine
        self.video_engine = video_engine
        self.router = router
        self.composer = composer
        self.max_parallel_images = max_parallel_images
        self._projects: dict[str, Project] = {}

    # ---- Bước 1+2: input -> scene planning (+ character lock) ----
    def create_project(self, script_text: str, reference_image_urls: list[str],
                        keep_character_consistent: bool, quota_mode: QuotaMode) -> Project:
        project = Project(
            id=str(uuid.uuid4())[:8],
            script_text=script_text,
            reference_image_urls=reference_image_urls,
            keep_character_consistent=keep_character_consistent,
            quota_mode=quota_mode,
        )
        style_hint = "generic cinematic style"
        if reference_image_urls:
            style_hint = self.vision.analyze_reference_image(reference_image_urls[0])

        project.scenes = self.vision.plan_scenes(script_text, style_hint)

        caps = self.video_engine.capabilities()
        project.chosen_technique = self.router.choose(len(project.scenes), quota_mode, caps)

        if keep_character_consistent and reference_image_urls:
            sheet_prompt = self.composer.character_sheet_prompt(style_hint)
            project.character_sheet_url = self.image_engine.generate_image(
                sheet_prompt, reference_image_url=reference_image_urls[0]
            )

        project._style_hint = style_hint  # lưu tạm dùng lại ở bước sau (không phải domain field chính thức)
        self._projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> Project:
        return self._projects[project_id]

    # ---- Bước 3: sinh ảnh cho từng scene, SONG SONG (giới hạn concurrency) ----
    def generate_scene_images(self, project_id: str) -> Project:
        project = self.get_project(project_id)
        style_hint = getattr(project, "_style_hint", "")
        ref = project.character_sheet_url or (project.reference_image_urls[0] if project.reference_image_urls else None)

        def _gen(scene: Scene) -> Scene:
            prompt = self.composer.scene_image_prompt(scene, style_hint)
            scene.image_url = self.image_engine.generate_image(prompt, reference_image_url=ref)
            scene.status = "image_ready"
            return scene

        with ThreadPoolExecutor(max_workers=self.max_parallel_images) as pool:
            futures = {pool.submit(_gen, s): s for s in project.scenes}
            for f in as_completed(futures):
                f.result()  # raise sớm nếu lỗi, ảnh khác không bị chặn nhờ as_completed
        return project

    # ---- Bước 3b: cho phép tạo lại 1 ảnh riêng lẻ (không đụng ảnh khác) ----
    def regenerate_single_image(self, project_id: str, scene_index: int) -> Scene:
        project = self.get_project(project_id)
        style_hint = getattr(project, "_style_hint", "")
        ref = project.character_sheet_url or (project.reference_image_urls[0] if project.reference_image_urls else None)
        scene = next(s for s in project.scenes if s.index == scene_index)
        prompt = self.composer.scene_image_prompt(scene, style_hint)
        scene.image_url = self.image_engine.generate_image(prompt, reference_image_url=ref)
        return scene

    # ---- Bước 4: submit video task(s) theo đúng technique đã chọn ----
    def start_video_generation(self, project_id: str) -> Project:
        project = self.get_project(project_id)
        style_hint = getattr(project, "_style_hint", "")
        technique = project.chosen_technique

        if technique == Technique.KEYFRAME_ARRAY:
            prompt = self.composer.keyframe_sequence_prompt(project.scenes, style_hint)
            urls = [s.image_url for s in project.scenes if s.image_url]
            total_duration = sum(s.duration_sec for s in project.scenes)
            task_id = self.video_engine.submit_keyframe_video(prompt, urls, total_duration)
            for s in project.scenes:
                s.video_task_id = task_id
                s.status = "queued"

        elif technique in (Technique.FRAME_TO_FRAME_CHAIN, Technique.SINGLE_SHOT_DIRECT):
            # Tuần tự bắt buộc theo tri thức: mỗi scene phụ thuộc frame trước.
            # Ở bản demo này (chưa có ffmpeg trích frame cuối), dùng lại chính
            # ảnh scene làm anchor — TODO khi có endpoint thật: trích frame cuối
            # video trước làm ảnh input cho scene sau, thay vì dùng lại ảnh gốc.
            for s in project.scenes:
                prompt = self.composer.scene_video_prompt(s, style_hint)
                s.video_task_id = self.video_engine.submit_single_image_video(
                    prompt, s.image_url, s.duration_sec
                )
                s.status = "queued"
        else:
            raise NotImplementedError(f"Technique {technique} chưa implement trong bản Agnes demo này")

        return project

    # ---- Polling: gộp trạng thái toàn bộ task đang chờ ----
    def poll_project_status(self, project_id: str) -> Project:
        project = self.get_project(project_id)
        seen_tasks: dict[str, dict] = {}
        for s in project.scenes:
            if not s.video_task_id or s.status == "completed":
                continue
            if s.video_task_id not in seen_tasks:
                seen_tasks[s.video_task_id] = self.video_engine.poll_task(s.video_task_id)
            result = seen_tasks[s.video_task_id]
            s.status = result["status"]
            if result["status"] == "completed":
                s.video_url = result["url"]
        if project.scenes and all(s.status == "completed" for s in project.scenes):
            # keyframe_array: mọi scene share cùng 1 video_url
            project.final_video_url = project.scenes[0].video_url
        return project


# ════════════════════════════════════════════════════════════════════════
# 5. PRESENTATION LAYER — Flask app + UI (HTML/JS nhúng, 4 bước theo mockup đã duyệt)
# ════════════════════════════════════════════════════════════════════════

def create_app(orchestrator: Orchestrator) -> Flask:
    app = Flask(__name__)

    @app.post("/api/projects")
    def api_create_project():
        body = request.get_json(force=True)
        try:
            project = orchestrator.create_project(
                script_text=body["script_text"],
                reference_image_urls=body.get("reference_image_urls", []),
                keep_character_consistent=bool(body.get("keep_character_consistent", False)),
                quota_mode=QuotaMode(body.get("quota_mode", QuotaMode.SAVE.value)),
            )
        except Exception as e:  # noqa: BLE001 — trả lỗi rõ ràng ra UI thay vì 500 trắng
            return jsonify({"error": str(e)}), 400
        return jsonify(_project_to_dict(project))

    @app.post("/api/projects/<pid>/images")
    def api_generate_images(pid):
        try:
            project = orchestrator.generate_scene_images(pid)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 400
        return jsonify(_project_to_dict(project))

    @app.post("/api/projects/<pid>/images/<int:scene_index>/regenerate")
    def api_regenerate_image(pid, scene_index):
        try:
            scene = orchestrator.regenerate_single_image(pid, scene_index)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 400
        return jsonify(dataclasses.asdict(scene))

    @app.post("/api/projects/<pid>/video")
    def api_start_video(pid):
        try:
            project = orchestrator.start_video_generation(pid)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 400
        return jsonify(_project_to_dict(project))

    @app.get("/api/projects/<pid>/status")
    def api_poll_status(pid):
        try:
            project = orchestrator.poll_project_status(pid)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 400
        return jsonify(_project_to_dict(project))

    @app.get("/")
    def index():
        return INDEX_HTML

    return app


def _project_to_dict(project: Project) -> dict:
    d = dataclasses.asdict(project)
    d.pop("_style_hint", None)
    return d


INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>AI Video Content Tool</title>
<style>
  body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#222;}
  h1{font-size:20px;}
  textarea{width:100%;min-height:80px;padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;}
  input[type=text]{width:100%;padding:8px;border:1px solid #ccc;border-radius:6px;font-size:14px;}
  .card{background:#fafafa;border:1px solid #e0e0e0;border-radius:10px;padding:16px;margin-bottom:14px;}
  .row{display:flex;justify-content:space-between;align-items:center;margin:8px 0;}
  button{padding:9px 14px;border-radius:6px;border:1px solid #999;background:#fff;cursor:pointer;font-size:14px;}
  button.primary{background:#222;color:#fff;border-color:#222;}
  button:disabled{opacity:.5;cursor:not-allowed;}
  .scene{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 12px;margin:6px 0;}
  .scene img{max-width:160px;display:block;margin-top:6px;border-radius:6px;}
  .badge{font-size:12px;padding:2px 8px;border-radius:12px;background:#eee;}
  .badge.completed{background:#d6f5df;color:#1a7431;}
  .badge.failed{background:#fbdada;color:#a11;}
  .step{display:none;}
  .step.active{display:block;}
  #err{color:#b00;font-size:13px;margin-top:8px;}
  video{width:100%;border-radius:8px;margin-top:10px;}
</style>
</head>
<body>
<h1>AI Video Content Tool — local (Agnes AI)</h1>

<div id="step1" class="step active card">
  <p><b>Bước 1 — Input</b></p>
  <p>Kịch bản:</p>
  <textarea id="script" placeholder="VD: video quảng cáo sản phẩm nước hoa, 3 cảnh..."></textarea>
  <p>URL ảnh mẫu (public HTTPS, cách nhau bằng dấu phẩy — có thể để trống):</p>
  <input type="text" id="refImages" placeholder="https://.../a.jpg, https://.../b.jpg">
  <div class="row">
    <label><input type="checkbox" id="lockChar" checked> Giữ nhân vật/sản phẩm nhất quán</label>
  </div>
  <div class="row">
    <label><input type="radio" name="quota" value="tiết_kiệm" checked> Tiết kiệm request</label>
    <label><input type="radio" name="quota" value="bình_thường"> Bình thường</label>
  </div>
  <button class="primary" onclick="createProject()">Tạo kế hoạch cảnh</button>
  <div id="err"></div>
</div>

<div id="step2" class="step card">
  <p><b>Bước 2 — Kịch bản đã chia scene</b> (technique: <span id="techName"></span>)</p>
  <div id="scenesList"></div>
  <button class="primary" onclick="genImages()">Sinh ảnh cho từng cảnh</button>
</div>

<div id="step3" class="step card">
  <p><b>Bước 3 — Duyệt ảnh trước khi tạo video</b></p>
  <div id="imagesList"></div>
  <button class="primary" onclick="startVideo()">Xác nhận, tạo video</button>
</div>

<div id="step4" class="step card">
  <p><b>Bước 4 — Render</b></p>
  <div id="statusList"></div>
  <div id="finalVideo"></div>
</div>

<script>
let projectId = null;
let pollTimer = null;

function showStep(n){
  document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));
  document.getElementById('step'+n).classList.add('active');
}
function showErr(msg){ document.getElementById('err').innerText = msg || ''; }

async function createProject(){
  showErr('');
  const script_text = document.getElementById('script').value.trim();
  if(!script_text){ showErr('Nhập kịch bản trước đã.'); return; }
  const refRaw = document.getElementById('refImages').value.trim();
  const reference_image_urls = refRaw ? refRaw.split(',').map(s=>s.trim()).filter(Boolean) : [];
  const keep_character_consistent = document.getElementById('lockChar').checked;
  const quota_mode = document.querySelector('input[name=quota]:checked').value;

  const res = await fetch('/api/projects', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({script_text, reference_image_urls, keep_character_consistent, quota_mode})});
  const data = await res.json();
  if(!res.ok){ showErr(data.error || 'Lỗi không rõ'); return; }
  projectId = data.id;
  document.getElementById('techName').innerText = data.chosen_technique;
  renderScenes(data.scenes);
  showStep(2);
}

function renderScenes(scenes){
  const el = document.getElementById('scenesList');
  el.innerHTML = scenes.map(s => `
    <div class="scene">
      <b>Cảnh ${s.index}</b> — ${s.description}<br>
      <small>${s.camera_move} · ~${s.duration_sec}s</small>
    </div>`).join('');
}

async function genImages(){
  showErr('');
  const res = await fetch(`/api/projects/${projectId}/images`, {method:'POST'});
  const data = await res.json();
  if(!res.ok){ showErr(data.error || 'Lỗi không rõ'); return; }
  renderImages(data.scenes);
  showStep(3);
}

function renderImages(scenes){
  const el = document.getElementById('imagesList');
  el.innerHTML = scenes.map(s => `
    <div class="scene">
      <b>Cảnh ${s.index}</b>
      ${s.image_url ? `<img src="${s.image_url}">` : '<i>chưa có ảnh</i>'}
      <div><button onclick="regen(${s.index})">Tạo lại ảnh này</button></div>
    </div>`).join('');
}

async function regen(idx){
  showErr('');
  const res = await fetch(`/api/projects/${projectId}/images/${idx}/regenerate`, {method:'POST'});
  const scene = await res.json();
  if(!res.ok){ showErr(scene.error || 'Lỗi không rõ'); return; }
  const card = document.querySelectorAll('#imagesList .scene')[idx-1];
  let img = card.querySelector('img');
  if(!img){ img = document.createElement('img'); card.insertBefore(img, card.querySelector('div')); }
  img.setAttribute('src', scene.image_url);
}

async function startVideo(){
  showErr('');
  const res = await fetch(`/api/projects/${projectId}/video`, {method:'POST'});
  const data = await res.json();
  if(!res.ok){ showErr(data.error || 'Lỗi không rõ'); return; }
  showStep(4);
  renderStatus(data.scenes);
  pollTimer = setInterval(pollStatus, 4000);
}

async function pollStatus(){
  const res = await fetch(`/api/projects/${projectId}/status`);
  const data = await res.json();
  renderStatus(data.scenes);
  if(data.final_video_url){
    clearInterval(pollTimer);
    document.getElementById('finalVideo').innerHTML = `<video controls src="${data.final_video_url}"></video>`;
  }
}

function renderStatus(scenes){
  const el = document.getElementById('statusList');
  el.innerHTML = scenes.map(s => `
    <div class="row"><span>Cảnh ${s.index}</span>
      <span class="badge ${s.status}">${s.status}</span></div>`).join('');
}
</script>
</body>
</html>
"""


# ════════════════════════════════════════════════════════════════════════
# 6. ENTRYPOINT / WIRING — nơi DUY NHẤT "ráp" abstraction với implementation cụ thể.
#    Muốn đổi sang Omni Flash sau này: viết OmniFlashVisionAnalyzer/ImageEngine/
#    VideoEngine (implement đúng 3 Port ở trên) rồi đổi 3 dòng khởi tạo dưới đây —
#    Orchestrator, Router, PromptComposer không cần sửa gì.
# ════════════════════════════════════════════════════════════════════════

def main():
    api_key = os.environ.get("AGNES_API_KEY")
    if not api_key:
        raise SystemExit(
            "Thiếu biến môi trường AGNES_API_KEY.\n"
            "Chạy: export AGNES_API_KEY='your_key_here'  (Linux/Mac)\n"
            "      set AGNES_API_KEY=your_key_here        (Windows cmd)\n"
        )

    http_client = AgnesHttpClient(api_key=api_key)
    vision = AgnesVisionAnalyzer(http_client)
    image_engine = AgnesImageEngine(http_client)
    video_engine = AgnesVideoEngine(http_client)

    orchestrator = Orchestrator(
        vision=vision,
        image_engine=image_engine,
        video_engine=video_engine,
        router=TechniqueRouter(),
        composer=PromptComposer(),
        max_parallel_images=4,
    )

    app = create_app(orchestrator)
    print("Đang chạy tại http://127.0.0.1:5000  (Ctrl+C để dừng)")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
