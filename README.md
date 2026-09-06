# Nghich_Tiep_Video — AI Product Video Tool

Công cụ tạo **video sản phẩm bằng AI** chạy local, với Agnes AI là generation engine.
Thay vì bắt người dùng tự viết kịch bản và tự chia scene, hệ thống hiện có một
**Creative Layer** để phân tích sản phẩm, định hướng ý tưởng, lập storyboard/shot
và giữ tính nhất quán trước khi giao việc cho generation pipeline.

## 1. Luồng hệ thống hiện tại

### Simple Mode — luồng khuyến nghị

Người dùng chỉ cần cung cấp:

- **Product**: một hoặc nhiều ảnh sản phẩm upload trực tiếp, hoặc URL ảnh public.
- **Goal**: mục tiêu video.
- **Platform**: TikTok, Instagram Reels, YouTube Shorts hoặc Facebook.
- **Duration**: thời lượng mong muốn.
- Có thể truyền thêm voiceover, background music và subtitle SRT cho bước hậu kỳ.

Luồng chính:

```text
Product Image / URL(s)
        + Goal
        + Platform
        + Duration
              │
              ▼
       ProductAnalyzer
              │
              ▼
       CreativeDirector
              │
              ▼
         CreativePlan
              │
              ▼
          SubjectLock
              │
              ▼
        ScenePlanner
              │
              ▼
         ShotPlanner
              │
              ▼
       PromptComposer
              │
              ▼
            Router
              │
              ▼
       Generation Pipeline
              │
              ▼
          Video Output
              │
              ▼
      Optional Post-processing
``` 

### Advanced / Legacy Mode

Hệ thống vẫn giữ pipeline cũ để tương thích với workflow thủ công: người dùng có
thể cung cấp script, style, subject, reference và lựa chọn quota/technique theo
cách cũ. Creative pipeline không thay thế các generation techniques hiện có mà
đứng phía trước chúng.

---

## 2. Creative Layer

### `core/product_analyzer.py`

Phân tích một hoặc nhiều product reference và tạo product profile có cấu trúc để
CreativeDirector sử dụng.

### `core/creative_director.py`

Đóng vai trò Creative Director: từ product profile + user input tạo ra
`CreativePlan`, gồm concept, script, style, character decision và scene direction.

### `core/platform_optimizer.py`

Cung cấp **platform guidance** cho CreativeDirector và ScenePlanner.
Hiện hỗ trợ:

- TikTok
- Instagram Reels
- YouTube Shorts
- Facebook

Guidance hiện bao gồm hook, pacing, text, CTA, shot duration và story structure.
Đây là **optimization guidance**, chưa phải deterministic hard constraint/validator.

### `models/creative_plan.py`

Model trung tâm của creative pipeline. Chứa input, concept, script, scenes và
các thông tin cần thiết để chuyển từ ý tưởng sang generation.

### `models/subject_lock.py`

Đại diện cho các reference cần giữ nhất quán, đặc biệt là product và character.
Product có thể có **nhiều reference images**.

### `core/scene_planner.py`

Chuyển CreativePlan thành scene plan. ScenePlanner nhận platform guidance và
creative context để xây dựng cấu trúc scene phù hợp.

### `core/shot_planner.py`

Lập kế hoạch shot bên trong từng scene. Mỗi shot có mô tả và generation prompt
nháp để PromptComposer tiếp tục chuẩn hóa.

### `models/shot_plan.py`

Model dữ liệu cho shot plan.

### `core/prompt_composer.py`

Ghép context thành final generation prompt theo thứ tự nhất quán:

```text
Global Consistency
→ Product Consistency
→ Character Consistency
→ Shot Description
→ Camera
→ Lighting
→ Motion
→ Negative Constraints
```

---

## 3. Multiple Product References

Simple Mode hỗ trợ nhiều product references.

Có thể dùng:

- nhiều URL ảnh;
- nhiều ảnh upload;
- kết hợp upload + URL.

Các reference được truyền xuyên suốt:

```text
Input
 ↓
CreativePlan.product_reference_urls[]
 ↓
SubjectLock
 ↓
PipelineInput.product_reference_urls[]
 ↓
TechniqueContext
 ↓
Generation
```

Khi generation technique hỗ trợ reference images, **toàn bộ product references**
được đưa vào generation context thay vì chỉ lấy ảnh đầu tiên.

Ảnh upload được chuyển thành **Data URI base64** trước khi đi vào creative/generation
pipeline. URL ảnh vẫn được giữ để tương thích với workflow cũ.

---

## 4. Generation Engine & Techniques

### `engines/`

```text
engines/
├── base_engine.py       # interface chung
└── agnes_client.py      # Agnes AI implementation
```

Generation layer được tách khỏi Creative Layer. Creative pipeline quyết định
**tạo gì**, còn engine/technique chịu trách nhiệm **gọi generation API**.

### `techniques/`

```text
techniques/
├── base.py
├── character_lock.py
├── single_shot_direct.py
├── keyframe_array.py
└── frame_to_frame_chain.py
```

Các technique dùng Strategy Pattern và cùng làm việc qua `BaseTechnique`.

`keyframe_array` và `frame_to_frame_chain` vẫn là các generation strategies hiện
tại. ShotPlanner/PromptComposer đã được nối vào runtime: shot prompts được tạo
trước và truyền vào technique context.

> Lưu ý kiến trúc: hiện tại shot plan **được compose vào scene-level generation
> prompt**. Mỗi `CreativeShot` chưa phải một video clip độc lập. Việc biến từng
> shot thành một generation job riêng là một thay đổi kiến trúc khác và chưa được
> coi là hoàn thành trong milestone này.

---

## 5. Orchestration

```text
orchestrator/
├── creative_pipeline_adapter.py
├── pipeline_runner.py
├── task_queue.py
└── polling_worker.py
```

### `creative_pipeline_adapter.py`

Cầu nối giữa Creative Layer và generation pipeline.

Nhiệm vụ chính:

- chuyển `CreativePlan` + `SubjectLock` thành generation input;
- truyền toàn bộ product references;
- đưa shot plans/prompts vào pipeline;
- map creative text/CTA và các input hậu kỳ thành `PostProcessOptions`.

### `pipeline_runner.py`

Nhạc trưởng generation pipeline: chọn technique, chuẩn bị context, generate image,
submit/poll video và thu kết quả cuối.

### `task_queue.py`

Quản lý task generation với concurrency giới hạn.

### `polling_worker.py`

Poll trạng thái video bất đồng bộ và cập nhật tiến độ real-time.

---

## 6. Post-processing

### `utils/video_post_processor.py`

Bước hậu kỳ tùy chọn sau khi generation hoàn thành:

```text
Generated Video
      │
      ▼
VideoPostProcessor
      │
      ├── Voiceover
      ├── Background Music
      ├── Subtitle / SRT
      ├── Text Overlay
      └── CTA
      │
      ▼
Final Video
```

Module này sử dụng FFmpeg và **không tự sinh voice/TTS/music bằng AI**. Các file
audio/subtitle bên ngoài là input tùy chọn. Text overlay và CTA có thể được map từ
CreativePlan.

---

## 7. Router

### `core/router.py`

Router quyết định generation technique dựa trên creative plan, capability của
engine và các constraint hiện có.

Các technique chưa được Agnes hỗ trợ vẫn được giữ trong kiến trúc để có thể bổ
sung engine khác sau này. Router sẽ fallback sang technique phù hợp khi capability
không đáp ứng.

---

## 8. Web UI

Chạy:

```bash
python app.py
```

Mặc định mở tại:

```text
http://127.0.0.1:8420
```

### Simple Mode

```text
Product image upload / Product URL(s)
Goal
Platform
Duration
        ↓
Start Creative Job
```

Có thể thêm tùy chọn:

```text
Voiceover
Background music
Subtitle SRT
```

### Advanced Mode

Dành cho workflow thủ công/legacy khi cần kiểm soát script, style, subject,
reference và technique/quota mode.

Progress của creative job được stream real-time qua WebSocket.

---

## 9. API chính

### Creative job

```text
POST /api/creative-jobs
```

Nhận input Simple Mode gồm product reference(s), goal, platform và duration.
Product reference có thể là URL hoặc ảnh upload.

### WebSocket progress

Server sử dụng WebSocket để stream log/progress của job tới Web UI.

---

## 10. CLI Legacy

Workflow CLI cũ vẫn được giữ:

```bash
python main.py \
  --script script.txt \
  --style "cinematic, warm lighting, photographic" \
  --subject "cô gái tóc dài áo dài trắng" \
  --reference https://example.com/anh-mau.jpg \
  --keep-character \
  --quota-mode tiet_kiem
```

Các tham số legacy vẫn bao gồm:

| Flag | Ý nghĩa |
|---|---|
| `--script` | File `.txt` kịch bản hoặc `-` để nhập stdin |
| `--style` | Style chung toàn video |
| `--subject` | Chủ thể chính |
| `--reference` | URL/data URI ảnh reference |
| `--keep-character` | Bật character lock |
| `--quota-mode` | `tiet_kiem` hoặc `binh_thuong` |
| `--output` | Thư mục lưu kết quả |

---

## 11. Cooldown & Key Rotation

`utils/key_rotation.py` quản lý nhiều Agnes API key và cooldown thích ứng.

Thiết kế hiện tại:

- cooldown nền: **3 phút**;
- lỗi/429/503: tăng **1 phút** mỗi lần;
- tối đa: **15 phút**;
- sau **3 lần generate thành công liên tiếp**: cooldown giảm dần;
- polling trạng thái video không dùng cooldown generate;
- concurrency generation mặc định là `1` để tránh dồn tải lên server.

Có thể chỉnh trong `.env`:

```text
COOLDOWN_BASE_SEC=180
COOLDOWN_MAX_SEC=900
COOLDOWN_STEP_SEC=60
COOLDOWN_DECAY_AFTER_SUCCESS=3
```

Nếu có nhiều key:

```text
AGNES_API_KEYS=key1,key2,key3
```

key rotation giúp một key đang cooldown không làm toàn bộ pipeline phải dừng nếu
còn key khác khả dụng.

---

## 12. Cài đặt

Yêu cầu:

- Python 3.10+
- FFmpeg trong `PATH`
- Agnes API key

Cài dependency:

```bash
pip install -r requirements.txt
```

Tạo `.env` từ `.env.example` và điền cấu hình cần thiết.

Windows có thể dùng:

```powershell
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

---

## 13. Kiểm thử

Chạy toàn bộ test suite:

```bash
pytest -q
```

Milestone hiện tại đã được kiểm thử với:

```text
103 passed
```

Ngoài unit tests cho từng module, test suite có coverage cho:

- CreativePlan
- ProductAnalyzer
- CreativeDirector
- SubjectLock
- ScenePlanner
- ShotPlanner
- PromptComposer
- Router
- Platform Optimizer
- Creative pipeline wiring
- Upload product image
- Multiple product references
- Post-processing flow
- Web UI contract

---

## 14. Kiến trúc tổng thể

```text
                    ┌──────────────────────┐
                    │      Simple UI       │
                    │ Product / Goal / ... │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   ProductAnalyzer    │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │   CreativeDirector   │◄── PlatformOptimizer
                    └──────────┬───────────┘
                               ▼
                       ┌──────────────┐
                       │ CreativePlan │
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │ SubjectLock  │
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │ ScenePlanner │◄── Platform guidance
                       └──────┬───────┘
                              ▼
                        ┌────────────┐
                        │ ShotPlanner│
                        └─────┬──────┘
                              ▼
                      ┌───────────────┐
                      │PromptComposer │
                      └───────┬───────┘
                              ▼
                         ┌─────────┐
                         │ Router  │
                         └────┬────┘
                              ▼
                  ┌──────────────────────┐
                  │ Generation Pipeline  │
                  │ Agnes + Techniques   │
                  └──────────┬───────────┘
                             ▼
                       Generated Video
                             │
                             ▼
                  ┌──────────────────────┐
                  │ VideoPostProcessor   │
                  │ optional FFmpeg step │
                  └──────────┬───────────┘
                             ▼
                         Final Video
```

---

## 15. Roadmap

Roadmap chi tiết nằm trong:

`Nghich_Tiep_Video_AI_Product_Video_Roadmap.md`

Các milestone creative chính đã hoàn thành gồm:

1. CreativePlan
2. ProductAnalyzer
3. CreativeDirector
4. Subject/Product Lock
5. ScenePlanner 2.0
6. ShotPlanner
7. PromptComposer 2.0
8. Router optimization
9. Simple + Advanced UI
10. Creative pipeline integration
11. Post-processing boundary/flow
12. Platform optimization guidance
13. Multiple Product References → Generation

Các hạng mục như deterministic platform validator hoặc generation thành clip độc
lập cho từng `CreativeShot` chưa được coi là hoàn thành trong milestone hiện tại.

---

## 16. Lưu ý

- Ảnh input cho Agnes phải là **public HTTPS URL hoặc Data URI base64** theo
  capability hiện tại của engine.
- Upload ảnh local trong Simple Mode được server chuyển sang Data URI trước khi
  truyền vào pipeline.
- `num_frames` được chuẩn hóa theo luật của engine trong `agnes_client.py`.
- Video generation không tự retry vô hạn; lỗi generation cần được xử lý theo
  policy của pipeline/key rotation.
- README này mô tả **kiến trúc hiện tại của code**, không phải workflow legacy
  ban đầu.
