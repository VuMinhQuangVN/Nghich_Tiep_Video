# Nghich_Tiep_Video — AI Video Tool
## Nâng cấp đợt 2: Agnes AI Modernization & Compatibility Roadmap

> **Mục tiêu:** Nâng cấp lớp Agnes AI của repo hiện tại theo bộ model mới, không đập lại pipeline.  
> **Nguyên tắc:** Stable trước, Experimental/Trial sau; mỗi task làm xong và test pass mới sang task tiếp theo.

---

# 1. Mục tiêu đợt 2

Repo hiện tại:

```text
User Input
   ↓
Product Analyzer
   ↓
Creative Director
   ↓
Creative Plan
   ↓
Subject Lock
   ↓
Scene Planner
   ↓
Shot Planner
   ↓
Prompt Composer
   ↓
Router
   ↓
Generation
   ↓
Post Processing
   ↓
Final Video
```

Đợt 2 chỉ tập trung chuẩn hóa Agnes AI phía dưới:

1. Sửa Agnes Client + SSL.
2. Dùng `agnes-2.5-flash` làm Brain chính.
3. Dùng `agnes-image-2.1-flash` làm Image Engine chính.
4. Giữ `agnes-video-v2.0` làm Stable/Fallback.
5. Bổ sung `agnes-video-2.5-flash` dạng Experimental.
6. Bổ sung `agnes-video-2.5` dạng Trial/Experimental.
7. Chuẩn hóa Video Job và polling.
8. Giữ multiple product references.
9. Chuẩn hóa retry/cooldown/key rotation.
10. Kiểm thử từng tầng rồi mới E2E.
11. Cuối cùng cập nhật Router, UI, Knowledge Base và README.

---

# 2. Kiến trúc Agnes mục tiêu

```text
                         AGNES AI
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
           TEXT           IMAGE          VIDEO
             │              │              │
             ▼              ▼              ▼
    agnes-2.5-flash  agnes-image-2.1  ┌───────────────┐
                                     │               │
                                     ▼               ▼
                              agnes-video-v2.0  Experimental
                                                 │
                                          ┌──────┴──────┐
                                          ▼             ▼
                                   2.5 Flash          2.5
```

| Model | Vai trò | Trạng thái |
|---|---|---|
| `agnes-2.5-flash` | Brain / Vision / Planning | PRIMARY |
| `agnes-image-2.1-flash` | Image generation/editing | PRIMARY |
| `agnes-video-v2.0` | Video generation | STABLE/FALLBACK |
| `agnes-video-2.5-flash` | Video generation | EXPERIMENTAL |
| `agnes-video-2.5` | Video generation | TRIAL/EXPERIMENTAL |

---

# 3. Nguyên tắc kiến trúc quan trọng

Pipeline không được phụ thuộc trực tiếp vào model Agnes.

Không rải:

```python
if model == "agnes-video-v2.0":
    ...
elif model == "agnes-video-2.5-flash":
    ...
```

khắp PipelineRunner/Technique.

Thay vào đó:

```text
Pipeline
   ↓
VideoEngine interface
   ↓
Agnes Video Adapter
   ├── V2.0
   ├── V2.5 Flash
   └── V2.5
```

Pipeline chỉ cần biết:

```python
submit_video(...)
poll_video(...)
download_video(...)
```

---

# 4. `agnes-2.5-flash` — Brain

## Vai trò

Dùng cho:

```text
ProductAnalyzer
CreativeDirector
ScenePlanner
ShotPlanner
PromptComposer
```

Tư duy:

```text
agnes-2.5-flash = Brain
```

## Endpoint

Base URL:

```text
https://apihub.agnes-ai.com/v1
```

Chat:

```text
POST /chat/completions
```

Tài liệu mới cũng có Responses API; abstraction nên để có thể chuyển endpoint mà không ảnh hưởng module phía trên.

## Image input

Docs `agnes-2.5-flash` mô tả image input bằng public image URL.

Vì vậy phải kiểm tra flow:

```text
Local Upload
    ↓
Data URI
    ↓
ProductAnalyzer
```

Không tự suy luận rằng Data URI được hỗ trợ ở model Text/Vision chỉ vì Image 2.1 hỗ trợ Data URI.

## Việc cần làm

- [ ] Đổi model mặc định sang `agnes-2.5-flash`.
- [ ] Test Chat Completions.
- [ ] Thiết kế abstraction cho Responses API.
- [ ] Test structured JSON.
- [ ] Test image understanding.
- [ ] Test public image URL.
- [ ] Xác định cách xử lý local upload cho ProductAnalyzer.
- [ ] Không phá ProductAnalyzer/CreativeDirector hiện tại.

---

# 5. `agnes-image-2.1-flash` — Image Engine

## Vai trò

```text
agnes-image-2.1-flash = Visual Engine
```

Endpoint:

```text
POST /images/generations
```

Hỗ trợ:

```text
Text → Image
Image → Image
Multiple Images → Image
```

## Multiple references

Phù hợp trực tiếp với tính năng Multiple Product References đã triển khai:

```text
Product Reference 1
Product Reference 2
Product Reference 3
        ↓
TechniqueContext
        ↓
Agnes Image Engine
        ↓
extra_body.image = [...]
```

Không được làm mất references trong:

```text
CreativePlan
→ PipelineInput
→ TechniqueContext
→ Technique
→ AgnesClient
```

## Ratio

Cần hỗ trợ các ratio:

```text
9:16
16:9
1:1
4:3
3:4
2:3
3:2
21:9
```

Platform mapping:

```text
TikTok         → 9:16
Instagram      → 9:16
YouTube Shorts → 9:16
Facebook       → 9:16 hoặc 1:1
YouTube        → 16:9
```

## Resolution

Không hard-code chỉ:

```text
1024x1024
```

Thiết kế theo:

```text
1K
2K
3K
4K
```

Nếu Agnes trả metadata normalization/size mapping thì response của Agnes là source of truth.

## Việc cần làm

- [ ] Đổi Image Engine sang `agnes-image-2.1-flash`.
- [ ] Chuẩn hóa `generate_image()`.
- [ ] Hỗ trợ multiple references.
- [ ] Hỗ trợ Data URI.
- [ ] Hỗ trợ public URL.
- [ ] Chuẩn hóa ratio.
- [ ] Chuẩn hóa resolution.
- [ ] Không để Technique tự xử lý chi tiết Agnes API.
- [ ] Test text-to-image.
- [ ] Test image-to-image.
- [ ] Test multiple-image composition.

---

# 6. `agnes-video-v2.0` — Stable Video Engine

**Không xóa V2.0.**

```text
agnes-video-v2.0
        ↓
STABLE
        ↓
FALLBACK
```

Endpoint:

```text
POST /videos
```

Ưu tiên kiến trúc dựa trên `video_id`; không xây mới dựa duy nhất vào legacy `task_id`.

## Việc cần làm

- [ ] Giữ V2.0.
- [ ] Chuẩn hóa submit.
- [ ] Chuẩn hóa response thành `VideoJob`.
- [ ] Chuẩn hóa polling.
- [ ] Chuẩn hóa download.
- [ ] Xử lý status.
- [ ] Xử lý lỗi.
- [ ] Làm fallback cho experimental.
- [ ] Test image-to-video.
- [ ] Test duration/resolution/ratio.
- [ ] Không hard-code output size nếu Agnes normalize.

---

# 7. `agnes-video-2.5-flash` — Experimental

Không đặt làm mặc định.

```env
AGNES_VIDEO_EXPERIMENTAL=false
AGNES_VIDEO_EXPERIMENTAL_MODEL=agnes-video-2.5-flash
```

Khi cần thử:

```env
AGNES_VIDEO_EXPERIMENTAL=true
```

Kiến trúc:

```text
Video Router
     │
     ├── Stable
     │     ↓
     │   V2.0
     │
     └── Experimental
           ↓
       2.5 Flash
```

Adapter phải tự xử lý mọi khác biệt về submit/polling.

Video Job nên hỗ trợ:

```text
video_id
model
status
progress
metadata
output URL
error
```

## Việc cần làm

- [ ] Adapter riêng.
- [ ] Không thay V2.0.
- [ ] Test submit.
- [ ] Test polling.
- [ ] Test image reference.
- [ ] Test output URL.
- [ ] Test quota/unavailable.
- [ ] Test fallback về V2.0.
- [ ] Chỉ bật bằng config.

---

# 8. `agnes-video-2.5` — Trial

Nếu tài khoản chỉ được trial thì **không được làm engine mặc định**.

```env
AGNES_VIDEO_25_ENABLED=false
AGNES_VIDEO_25_MODEL=agnes-video-2.5
```

Flow:

```text
Request
   ↓
Video 2.5
   ↓
Success → continue
   ↓
Failure/unavailable
   ↓
V2.0 fallback
```

Không retry vô hạn.

Không để trial trở thành dependency bắt buộc của Simple Mode.

## Việc cần làm

- [ ] Adapter riêng.
- [ ] Config flag.
- [ ] Test availability.
- [ ] Test submit.
- [ ] Test polling.
- [ ] Test fallback.
- [ ] Test entitlement/quota failure.
- [ ] Không để Simple Mode tự động chọn trial.

---

# 9. Agnes Client — P0 quan trọng nhất

File trọng tâm:

```text
engines/agnes_client.py
```

Audit:

```text
SSL
Base URL
API key
Headers
Chat
Image
Video
Polling
Download
Timeout
Retry
Error mapping
```

## SSL hiện tại

Máy Windows đã chứng minh:

```text
curl.exe
    ↓
apihub.agnes-ai.com
    ↓
TLS OK
    ↓
HTTP 404 Invalid URL
```

HTTP 404 ở `/v1` là bình thường vì `/v1` là base URL, không phải GET endpoint.

Trong khi app Python đang:

```text
Python/aiohttp
    ↓
CERTIFICATE_VERIFY_FAILED
```

Do đó:

- [ ] Kiểm tra aiohttp.
- [ ] Kiểm tra certifi.
- [ ] Kiểm tra Python/OpenSSL.
- [ ] Kiểm tra SSL context.
- [ ] Kiểm tra proxy/HTTPS inspection nếu cần.
- [ ] Viết test kết nối riêng.
- [ ] Không dùng `ssl=False`.
- [ ] Không dùng `verify=False`.
- [ ] Không đổi endpoint chỉ để né lỗi khi chưa xác định nguyên nhân.

---

# 10. Model Configuration

Không rải model name trong code.

Đề xuất `.env`:

```env
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1

AGNES_TEXT_MODEL=agnes-2.5-flash
AGNES_IMAGE_MODEL=agnes-image-2.1-flash

AGNES_VIDEO_MODEL=agnes-video-v2.0

AGNES_VIDEO_EXPERIMENTAL=false
AGNES_VIDEO_EXPERIMENTAL_MODEL=agnes-video-2.5-flash

AGNES_VIDEO_25_ENABLED=false
AGNES_VIDEO_25_MODEL=agnes-video-2.5
```

Nếu cần alternate route:

```env
AGNES_ALTERNATE_BASE_URL=https://apihub.agnes-ai.cn/v1
```

Alternate chỉ dùng khi có lý do network/DNS/TLS/route phù hợp.

---

# 11. VideoJob abstraction

Không để Pipeline phụ thuộc `task_id`.

Thiết kế:

```python
VideoJob(
    video_id,
    model,
    status,
    progress=None,
    output_url=None,
    error=None,
    metadata=None,
)
```

Flow:

```text
submit_video()
      ↓
VideoJob
      ↓
poll_video()
      ↓
VideoJob updated
      ↓
completed
      ↓
download_video()
```

V2.0, 2.5 Flash và 2.5 đều map về abstraction này.

---

# 12. Reference Pipeline

Chuẩn hóa:

```text
ImageReference
```

Có thể có:

```text
type:
    public_url
    data_uri

role:
    product
    character
    style

source
index
```

Flow:

```text
User
 ↓
Product Images / URLs
 ↓
ProductAnalyzer
 ↓
CreativePlan
 ↓
SubjectLock
 ↓
PipelineInput
 ↓
TechniqueContext
 ↓
Image/Video Engine
```

Multiple references phải được giữ nguyên.

---

# 13. Router nâng cấp

Router hiện tại đã xử lý technique.

Đợt 2 bổ sung:

```text
Router
├── choose_technique()
├── choose_image_model()
├── choose_video_model()
└── choose_fallback()
```

Ví dụ:

```text
Normal request
→ V2.0

Experimental enabled
→ 2.5 Flash

Explicit trial
→ 2.5
```

Nếu experimental/trial lỗi:

```text
Experimental
    ↓
failure
    ↓
V2.0
```

---

# 14. Retry / Error Policy

## Có thể retry

```text
timeout
connection reset
temporary network error
5xx
429
```

## Không retry vô hạn

```text
401
403
invalid API key
invalid request
unsupported parameter
invalid model
```

## Fallback

```text
2.5 Flash
    ↓
temporary failure
    ↓
V2.0
```

```text
2.5 Trial
    ↓
trial unavailable
    ↓
V2.0
```

---

# 15. Cooldown / Key Rotation

Giữ logic hiện tại:

```text
Base cooldown = 3 minutes
Error        = +1 minute
Maximum      = 15 minutes
3 successes  = decrease cooldown
```

Polling không bị cooldown.

Key rotation tách khỏi model selection.

Không:

```text
model error
→ đổi API key vô hạn
```

Ví dụ:

```text
401 invalid key
→ mark key invalid
→ rotate key
```

nhưng:

```text
400 invalid request
→ sửa request
```

không phải rotate key.

---

# 16. Test Strategy

Không chạy E2E ngay.

## Level 1 — Connectivity

```text
[ ] curl / Agnes endpoint
[ ] Python SSL
[ ] aiohttp SSL
[ ] API key
```

## Level 2 — Brain

```text
[ ] agnes-2.5-flash text
[ ] structured JSON
[ ] image URL understanding
```

## Level 3 — Image

```text
[ ] Image 2.1 text → image
[ ] Image 2.1 image → image
[ ] Image 2.1 multiple references
[ ] Image 2.1 Data URI
[ ] Image 2.1 URL
```

## Level 4 — Stable Video

```text
[ ] V2.0 submit
[ ] V2.0 poll
[ ] V2.0 download
[ ] V2.0 image → video
```

## Level 5 — Experimental

```text
[ ] 2.5 Flash submit
[ ] 2.5 Flash poll
[ ] 2.5 Flash download
[ ] 2.5 Flash fallback
```

## Level 6 — Trial

```text
[ ] 2.5 availability
[ ] 2.5 submit
[ ] 2.5 poll
[ ] 2.5 fallback
```

## Level 7 — E2E

```text
Product
 ↓
Analyzer
 ↓
Director
 ↓
Scene
 ↓
Shot
 ↓
Prompt
 ↓
Image
 ↓
Video
 ↓
Post Process
 ↓
Final MP4
```

---

# 17. Simple Mode

Simple Mode không expose chi tiết Agnes mặc định.

User chỉ cần:

```text
Product Image(s)
Product URL(s)
Goal
Platform
Duration
```

System:

```text
Brain  → 2.5 Flash
Image  → Image 2.1 Flash
Video  → V2.0
```

Experimental chỉ bật từ Advanced Mode hoặc config rõ ràng.

---

# 18. Advanced Mode

Cho phép:

```text
Video Engine:
    Auto
    V2.0 Stable
    2.5 Flash Experimental
    2.5 Trial
```

Hiển thị rõ:

```text
2.5 Flash = Experimental
2.5 = Trial
```

Không để người dùng bình thường vô tình dùng trial.

---

# 19. Post Processing

Giữ pipeline hiện tại:

```text
Generated Video
      ↓
VideoPostProcessor
      ├── Voiceover
      ├── Music
      ├── Subtitle
      ├── Text Overlay
      └── CTA
      ↓
Final Video
```

Thay Agnes model không được làm ảnh hưởng Post Processing.

---

# 20. Platform Optimization

Giữ Phase 12 hiện tại:

```text
TikTok
Instagram Reels
YouTube Shorts
Facebook
```

Đây hiện là guidance cho AI, chưa phải hard validator.

Không trộn hard enforcement vào Agnes modernization.

---

# 21. Knowledge Base

Cập nhật:

```text
knowledge-base/
├── agnes-2.5-flash.md
├── agnes-image-2.1-flash.md
├── agnes-video-v2.0.md
├── agnes-video-2.5-flash.md
├── agnes-video-2.5.md
└── agnes-integration.md
```

Mỗi model ghi:

```text
Endpoint
Model
Input
Request
Response
Reference support
Ratio
Resolution
Duration
Polling
Errors
Limitations
Fallback
```

Nguồn ưu tiên:

1. Agnes official docs.
2. Agnes official GitHub.
3. Runtime test thực tế.
4. Nguồn cộng đồng chỉ dùng để bổ sung troubleshooting.

---

# 22. Thứ tự triển khai chính thức

## P0 — Runtime Recovery

**Làm đầu tiên.**

```text
1. Audit AgnesClient
2. Fix Python SSL
3. Verify Base URL
4. Verify API key
5. Verify aiohttp
6. Verify basic Agnes request
```

Chưa đụng Video 2.5.

---

## P1 — Model Configuration

```text
7. Centralize model config
8. Centralize endpoint config
9. Centralize capability config
```

---

## P2 — Brain Upgrade

```text
10. agnes-2.5-flash
11. ProductAnalyzer
12. CreativeDirector
13. ScenePlanner
14. ShotPlanner
15. PromptComposer
```

---

## P3 — Image Upgrade

```text
16. agnes-image-2.1-flash
17. Image reference abstraction
18. Multiple product references
19. Ratio
20. Resolution
21. Image tests
```

---

## P4 — Stable Video

```text
22. V2.0 adapter
23. VideoJob abstraction
24. Submit
25. Poll
26. Download
27. V2.0 tests
```

---

## P5 — Experimental Video

```text
28. 2.5 Flash adapter
29. Experimental config
30. Polling
31. Download
32. Fallback to V2.0
33. Experimental tests
```

---

## P6 — Trial Video

```text
34. 2.5 adapter
35. Trial config
36. Availability
37. Polling
38. Fallback
39. Trial tests
```

---

## P7 — Router

```text
40. Model selection
41. Capability selection
42. Fallback selection
43. Error-aware routing
```

---

## P8 — Reliability

```text
44. Retry
45. Cooldown
46. Key rotation
47. Timeout
48. Error mapping
```

---

## P9 — E2E

```text
49. Simple Mode
50. Advanced Mode
51. Product → Final Video
52. Post Processing
```

---

## P10 — Finalization

```text
53. Knowledge Base
54. README
55. Architecture diagram
56. Test suite
57. Runtime smoke test
```

---

# 23. Definition of Done

```text
[ ] Python kết nối Agnes không lỗi SSL
[ ] agnes-2.5-flash chạy ổn
[ ] Image 2.1 Flash chạy ổn
[ ] Multiple product references hoạt động
[ ] V2.0 tạo video được
[ ] V2.0 polling/download ổn
[ ] 2.5 Flash có adapter riêng
[ ] 2.5 Flash không phải dependency bắt buộc
[ ] 2.5 có adapter riêng
[ ] Trial không phá Simple Mode
[ ] Experimental có config flag
[ ] Fallback về V2.0 hoạt động
[ ] Retry không vô hạn
[ ] 401/400 được phân loại đúng
[ ] Simple Mode E2E chạy
[ ] Post Processing vẫn hoạt động
[ ] Tests pass
[ ] README/Knowledge Base cập nhật
```

---

# 24. Không được làm trong đợt này

```text
❌ Viết lại toàn bộ PipelineRunner
❌ Bỏ ScenePlanner
❌ Bỏ ShotPlanner
❌ Bỏ PromptComposer
❌ Bỏ SubjectLock
❌ Xóa V2.0
❌ Lấy Video 2.5 Trial làm default
❌ Lấy Video 2.5 Flash làm default khi chưa test
❌ Disable SSL verification
❌ Retry vô hạn
❌ Đổi endpoint chỉ vì lỗi chưa xác định
❌ Biến mỗi CreativeShot thành một video clip riêng nếu chưa có quyết định kiến trúc
❌ Làm hard platform validator trong đợt này
```

---

# 25. Kiến trúc đích

```text
                         USER
                           │
                           ▼
                    Simple / Advanced
                           │
                           ▼
                  Creative Pipeline
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       ANALYSIS          IMAGE            VIDEO
          │                │                │
          ▼                ▼                ▼
  Agnes 2.5 Flash   Image 2.1 Flash     VideoEngine
          │                │                │
          │                │         ┌──────┼──────┐
          │                │         │      │      │
          │                │         ▼      ▼      ▼
          │                │        V2.0  2.5F   2.5
          │                │       STABLE EXP.   TRIAL
          │                │         │      │      │
          │                │         └──────┴──────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                           ▼
                    Post Processing
                           │
                           ▼
                       Final MP4
```

---

# 26. Quy tắc làm việc

Mỗi task:

```text
1. Đọc code hiện tại
2. Đọc Agnes docs hiện tại
3. Xác định gap
4. Sửa đúng phạm vi
5. Viết regression test
6. Chạy targeted tests
7. Chạy full test suite
8. Compile check
9. Giao CHỈ file thay đổi
10. User apply
11. User xác nhận pass
12. Mới sang task tiếp theo
```

**Không nhảy task.**

---

# 27. TASK HIỆN TẠI

## P0.1 — Agnes Client & SSL Audit

Chỉ tập trung vào:

```text
engines/agnes_client.py
config.py
requirements.txt
```

và test cần thiết.

Mục tiêu:

```text
Python
  ↓
aiohttp
  ↓
HTTPS
  ↓
https://apihub.agnes-ai.com/v1
  ↓
Agnes
```

phải hoạt động.

Sau khi P0.1 pass:

```text
P0.2 — Agnes API Smoke Test
```

Sau đó:

```text
P1 — Model Configuration
```

**Không chuyển sang Video 2.5 trước khi nền tảng Agnes Client ổn định.**

---

# 28. Tài liệu Agnes tham chiếu

- `agnes-2.5-flash`  
  https://agnes-ai.com/en/docs/agnes-25-flash

- `agnes-image-2.1-flash`  
  https://agnes-ai.com/en/docs/agnes-image-21-flash

- `agnes-video-v2.0`  
  https://agnes-ai.com/en/docs/agnes-video-v20

- `agnes-video-2.5-flash`  
  https://agnes-ai.com/en/docs/agnes-video-25-flash

- `agnes-video-2.5`  
  https://agnes-ai.com/en/docs/agnes-video-25

- Agnes official repository  
  https://github.com/AgnesAI-Labs/AgnesAI-Models

> Model availability, quota, trial và entitlement có thể phụ thuộc tài khoản/API key. Vì vậy Video 2.5/2.5 Flash được thiết kế dạng Experimental/Trial thay vì trở thành dependency bắt buộc.
