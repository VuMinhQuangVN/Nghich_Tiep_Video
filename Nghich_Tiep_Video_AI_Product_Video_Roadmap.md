# Nghich_Tiep_Video — AI Product Video Generator

## Master Roadmap & Implementation Specification

> Mục tiêu: biến `Nghich_Tiep_Video` từ tool "người dùng tự nghĩ kịch bản → AI tạo video"
> thành hệ thống "người dùng đưa ảnh sản phẩm + mục tiêu → AI tự làm đạo diễn → tạo video quảng cáo".
>
> **QUY TẮC:** Chưa code toàn bộ một lúc. Làm đúng thứ tự từng Phase. Mỗi Phase hoàn thành và test ổn mới sang Phase tiếp theo.

---

# 1. TẦM NHÌN CUỐI CÙNG

Người dùng chỉ cần cung cấp:

- Ảnh sản phẩm hoặc URL ảnh public
- Mục tiêu video
- Nền tảng đăng video
- Thời lượng mong muốn

Ví dụ:

```text
Product:
https://example.com/shoe.jpg

Goal:
Video quảng cáo bán hàng

Platform:
TikTok

Duration:
30 giây
```

Hệ thống tự quyết định:

```text
Product Analysis
        ↓
Target Audience
        ↓
Marketing Concept
        ↓
Visual Style
        ↓
Character / Model (nếu cần)
        ↓
Script
        ↓
Storyboard
        ↓
Shot Plan
        ↓
Product / Character Consistency
        ↓
Image Generation
        ↓
Video Generation
        ↓
FFmpeg Assembly
        ↓
Final Video
```

---

# 2. NGUYÊN TẮC KIẾN TRÚC

Không phá bỏ pipeline generation hiện tại.

Giữ lại nền tảng:

```text
PipelineRunner
ScenePlanner
Router
Techniques
BaseEngine
AgnesClient
PollingWorker
TaskQueue
FFmpeg
```

Thay vào đó, xây thêm một tầng "AI Creative" phía trước generation pipeline.

Kiến trúc mục tiêu:

```text
USER INPUT
   ↓
CREATIVE DIRECTOR
   ↓
CREATIVE PLAN
   ↓
SCENE / SHOT PLANNING
   ↓
REFERENCE / CONSISTENCY
   ↓
EXISTING GENERATION PIPELINE
   ↓
FINAL VIDEO
```

Ý tưởng quan trọng:

> **Generation Engine không phải bộ não.**
> Engine chỉ thực hiện kế hoạch mà Creative layer tạo ra.

---

# 3. PHASE 1 — ĐẶT NỀN DỮ LIỆU CREATIVE

## Mục tiêu

Tạo cấu trúc dữ liệu trung gian `CreativePlan`.

Chưa cần thay UI.
Chưa cần thay Agnes.
Chưa cần làm AI tự động hoàn toàn.

Tạo một "hợp đồng dữ liệu" để các Phase sau cùng dùng chung.

## CreativePlan dự kiến

```text
CreativePlan
├── input
│   ├── product_reference_urls[]
│   ├── goal
│   ├── platform
│   ├── duration_sec
│   └── language
│
├── product
│   ├── name
│   ├── category
│   ├── description
│   ├── visual_identity
│   └── selling_points[]
│
├── audience
│   ├── age_range
│   ├── gender
│   ├── interests[]
│   └── pain_points[]
│
├── concept
│   ├── title
│   ├── description
│   └── hook
│
├── visual_style
│   ├── style
│   ├── lighting
│   ├── color_palette
│   ├── camera_style
│   └── mood
│
├── character
│   ├── required
│   ├── description
│   └── reference_url
│
├── script
│   ├── voiceover
│   ├── text_overlays[]
│   └── cta
│
└── scenes[]
```

## Điều kiện hoàn thành

Có thể tạo một `CreativePlan` bằng dữ liệu test mà không cần gọi AI.

---

# 4. PHASE 2 — PRODUCT ANALYZER

## Mục tiêu

AI nhìn ảnh sản phẩm và hiểu sản phẩm là gì.

Input:

```text
product_reference_urls[]
```

Output:

```text
ProductProfile
```

AI cần nhận diện tối thiểu:

- Tên / loại sản phẩm
- Category
- Hình dáng
- Màu sắc
- Chất liệu nhìn thấy được
- Logo / branding nhìn thấy được
- Các đặc điểm nhận diện
- Điểm nổi bật
- Bối cảnh sử dụng phù hợp
- Những chi tiết phải giữ nguyên khi generate

Ví dụ:

```text
Product:
Sneaker

Visual identity:
- White upper
- Black sole
- Low-top
- Red logo
- White shoelaces

Consistency requirements:
- Do not change logo
- Do not change sole shape
- Do not change dominant colors
```

## Quan trọng

Không chỉ phân tích "đây là đôi giày".

Phải tạo ra **Product Identity** để các scene sau dùng làm reference.

---

# 5. PHASE 3 — AI CREATIVE DIRECTOR

## Đây là bộ não chính.

Input:

```text
ProductProfile
+
Goal
+
Platform
+
Duration
+
Language
```

AI tự quyết định:

```text
Target Audience
Concept
Hook
Visual Style
Character requirement
Script direction
CTA
```

Ví dụ:

```text
Product:
Lipstick

Goal:
Sell product

Platform:
TikTok

Duration:
30 sec
```

AI có thể tạo:

```text
Concept:
"5 seconds to transform your look"

Style:
Luxury beauty commercial

Lighting:
Soft diffused beauty lighting

Character:
Female model, 22-28

Hook:
Close-up opening shot

CTA:
Discover your shade
```

## Quy tắc

Người dùng không bắt buộc phải nhập:

- Script
- Style
- Subject
- Character

AI tự tạo các phần này.

Người dùng vẫn có thể override ở chế độ Advanced sau này.

---

# 6. PHASE 4 — REFERENCE / SUBJECT LOCK

## Đổi tư duy từ Character Lock → Subject Consistency

Không phải video nào cũng có nhân vật.

Subject có thể là:

```text
PRODUCT
CHARACTER
OBJECT
```

Mục tiêu:

```text
Reference Image
      ↓
Reference Analyzer
      ↓
Subject Profile
      ↓
Reference Sheet
      ↓
Tất cả scene dùng cùng reference
```

## Product Lock

Đảm bảo sản phẩm nhất quán:

- Shape
- Color
- Logo
- Packaging
- Texture
- Important details

## Character Lock

Nếu Creative Director quyết định cần người mẫu:

- Face
- Hair
- Clothing
- Body proportions
- Identity
- Visual style

## Quy tắc

AI phải tự quyết định:

```text
Cần character?
YES / NO
```

Ví dụ:

```text
Blender:
NO character

Lipstick:
YES character

Sneaker:
Có thể YES hoặc NO tùy concept
```

---

# 7. PHASE 5 — SCENE PLANNER 2.0

`scene_planner.py` hiện tại đang tạo scene với:

```text
index
description
duration_sec
camera_move
```

Giữ các field này nhưng mở rộng.

Scene mục tiêu:

```text
Scene
├── index
├── objective
├── description
├── duration_sec
├── camera
├── camera_motion
├── framing
├── product_visibility
├── product_position
├── character_action
├── environment
├── lighting
├── mood
├── transition
├── voiceover
├── text_overlay
└── cta
```

Ví dụ:

```text
Scene 3

Objective:
Demonstrate lipstick application

Duration:
5 sec

Camera:
Close-up

Camera motion:
Slow push-in

Product:
Visible in hand

Character:
Applies lipstick

Lighting:
Soft beauty lighting

Voiceover:
"Chỉ một lớp..."

Transition:
Match cut
```

---

# 8. PHASE 6 — SHOT PLANNER

Scene và Shot là hai cấp độ khác nhau.

```text
Scene
 ↓
Shot 1
Shot 2
Shot 3
```

Ví dụ:

```text
Scene 1 — Product Introduction

Shot 1:
Macro product shot

Shot 2:
Camera rotates around product

Shot 3:
Product hero shot
```

Shot cần mô tả:

```text
Shot
├── shot_type
├── framing
├── camera_angle
├── camera_motion
├── subject_position
├── action
├── environment
├── lighting
├── duration
└── generation_prompt
```

Mục tiêu:

> AI không chỉ nghĩ "scene này có gì", mà phải nghĩ "camera thực sự quay như thế nào".

---

# 9. PHASE 7 — PROMPT COMPOSER 2.0

Hiện tại `prompt_composer.py` đang ghép prompt từ scene + style + subject.

Nâng thành:

```text
Product Identity
+
Character Identity
+
Global Style
+
Scene
+
Shot
+
Camera
+
Lighting
+
Motion
+
Consistency Rules
```

Tạo prompt cuối cùng cho engine.

Cấu trúc:

```text
GLOBAL CONSISTENCY
+
PRODUCT CONSISTENCY
+
CHARACTER CONSISTENCY
+
SHOT DESCRIPTION
+
CAMERA
+
LIGHTING
+
MOTION
+
NEGATIVE CONSTRAINTS
```

Không để mỗi scene tự "sáng tạo lại" sản phẩm.

---

# 10. PHASE 8 — ROUTER / TECHNIQUE

Giữ Router hiện tại làm nền.

Router tự quyết định technique.

Người dùng bình thường không cần chọn:

```text
quota_mode
technique
concurrency
```

Luồng:

```text
CreativePlan
     ↓
Router
     ↓
Technique phù hợp
```

Ví dụ:

```text
1 scene
→ single_shot_direct

nhiều scene + keyframe support
→ keyframe_array

cần kiểm soát từng scene
→ frame_to_frame_chain

engine hỗ trợ edit
→ scene_extend_edit
```

Advanced Settings mới cho phép developer override.

---

# 11. PHASE 9 — UI 2 CHẾ ĐỘ

## Simple Mode

UI cực đơn giản:

```text
AI PRODUCT VIDEO

[ Product Image / URL ]

Mục tiêu:
[ Video quảng cáo bán hàng ]

Platform:
[ TikTok ]

Duration:
[ 30s ]

[ ✓ AI tự viết kịch bản ]
[ ✓ AI tự chọn style ]
[ ✓ AI tự quyết định nhân vật ]
[ ✓ Giữ sản phẩm nhất quán ]

          [ TẠO VIDEO ]
```

## Advanced Mode

Cho phép chỉnh:

```text
Script
Style
Character
Reference URL
Technique
Concurrency
Engine
```

Simple Mode dành cho người dùng.

Advanced Mode dành cho developer / power user.

---

# 12. PHASE 10 — GENERATION PIPELINE

Không viết lại toàn bộ.

Creative layer tạo:

```text
CreativePlan
```

Sau đó adapter chuyển CreativePlan sang input mà pipeline hiện tại hiểu.

```text
CreativePlan
      ↓
PipelineInput
      ↓
PipelineRunner
      ↓
Technique
      ↓
Engine
      ↓
Video
```

Đây là nguyên tắc quan trọng để tránh phá code cũ.

---

# 13. PHASE 11 — VIDEO POST-PROCESSING

Sau generation mới mở rộng:

```text
Video
 ↓
FFmpeg
 ├── concatenate
 ├── voiceover
 ├── subtitles
 ├── text overlay
 ├── background music
 └── CTA
```

Không làm voice/subtitle/music ngay từ đầu.

Để sau khi core generation ổn định.

---

# 14. PHASE 12 — PLATFORM OPTIMIZATION

Creative Director nhận:

```text
TikTok
Instagram Reels
YouTube Shorts
Facebook
```

Từ đó tự điều chỉnh:

```text
Hook
Pacing
Text
CTA
Shot duration
Story structure
```

Ví dụ TikTok:

```text
0-3s:
Strong hook

3-20s:
Product demonstration

20-27s:
Benefit

27-30s:
CTA
```

---

# 15. KIẾN TRÚC THƯ MỤC MỤC TIÊU

Không cần tạo tất cả ngay.

Mục tiêu cuối:

```text
Nghich_Tiep_Video/
│
├── app.py
├── main.py
├── config.py
├── requirements.txt
├── .env.example
│
├── core/
│   ├── creative_director.py
│   ├── product_analyzer.py
│   ├── reference_analyzer.py
│   ├── scene_planner.py
│   ├── shot_planner.py
│   ├── router.py
│   └── prompt_composer.py
│
├── models/
│   ├── creative_plan.py
│   ├── product_profile.py
│   ├── character_profile.py
│   ├── scene.py
│   └── shot.py
│
├── references/
│   ├── subject_lock.py
│   ├── product_lock.py
│   └── character_lock.py
│
├── engines/
│   ├── base_engine.py
│   └── agnes_client.py
│
├── techniques/
│
├── orchestrator/
│
├── utils/
│
├── static/
│
└── knowledge-base/
    ├── creative-director.md
    ├── product-video.md
    ├── reference-lock.md
    ├── scene-planning.md
    └── shot-planning.md
```

**Không tạo toàn bộ cây này ngay.**
Chỉ tạo khi tới Phase tương ứng.

---

# 16. THỨ TỰ IMPLEMENT BẮT BUỘC

```text
PHASE 1
CreativePlan
     ↓
PHASE 2
ProductAnalyzer
     ↓
PHASE 3
CreativeDirector
     ↓
PHASE 4
Subject/Product Lock
     ↓
PHASE 5
ScenePlanner 2.0
     ↓
PHASE 6
ShotPlanner
     ↓
PHASE 7
PromptComposer 2.0
     ↓
PHASE 8
Router optimization
     ↓
PHASE 9
UI Simple + Advanced
     ↓
PHASE 10
Connect existing Pipeline
     ↓
PHASE 11
Post-processing
     ↓
PHASE 12
Platform optimization
```

---

# 17. ĐIỀU KHÔNG ĐƯỢC LÀM

## Không làm ngay:

- Voice cloning
- Music generation
- Subtitle AI
- Multi-engine phức tạp
- User accounts
- Database
- Cloud deployment
- Payment
- Analytics

Core product trước:

```text
Ảnh sản phẩm
     ↓
AI hiểu sản phẩm
     ↓
AI nghĩ concept
     ↓
AI viết script
     ↓
AI chọn style
     ↓
AI tạo storyboard
     ↓
AI giữ product/model consistency
     ↓
Video
```

---

# 18. DEFINITION OF DONE

Project được coi là đạt MVP khi người dùng có thể:

```text
1. Đưa ảnh sản phẩm / URL
2. Chọn mục tiêu
3. Chọn platform
4. Chọn thời lượng
5. Bấm "Tạo video"
```

và hệ thống tự:

```text
✓ Phân tích sản phẩm
✓ Tạo Product Profile
✓ Chọn target audience
✓ Tạo concept
✓ Tạo hook
✓ Chọn visual style
✓ Quyết định có cần character
✓ Tạo script
✓ Tạo scenes
✓ Tạo shots
✓ Giữ product consistency
✓ Chọn technique
✓ Generate video
✓ Ghép video
✓ Xuất final.mp4
```

---

# 19. NGUYÊN TẮC LÀM VIỆC TỪ GIỜ

Mỗi lần bắt đầu một Phase:

1. Đọc file này.
2. Xác định Phase hiện tại.
3. Chỉ sửa những phần thuộc Phase đó.
4. Không tự ý nhảy Phase.
5. Test Phase hiện tại.
6. Khi ổn mới đánh dấu `[DONE]`.
7. Sau đó mới sang Phase tiếp theo.

Trạng thái ban đầu:

```text
[ ] Phase 1 — CreativePlan
[ ] Phase 2 — ProductAnalyzer
[ ] Phase 3 — CreativeDirector
[ ] Phase 4 — Subject/Product Lock
[ ] Phase 5 — ScenePlanner 2.0
[ ] Phase 6 — ShotPlanner
[ ] Phase 7 — PromptComposer 2.0
[ ] Phase 8 — Router optimization
[ ] Phase 9 — UI
[ ] Phase 10 — Generation integration
[ ] Phase 11 — Post-processing
[ ] Phase 12 — Platform optimization
```

---

# 20. PHASE HIỆN TẠI

**Bắt đầu từ Phase 1 — CreativePlan.**

Chưa làm ProductAnalyzer.
Chưa làm CreativeDirector.
Chưa sửa UI.
Chưa sửa Agnes.
Chưa sửa Technique.

Mục tiêu đầu tiên duy nhất:

> **Tạo được một cấu trúc `CreativePlan` sạch, ổn định và đủ khả năng chứa toàn bộ kế hoạch video mà các Phase sau sẽ tạo ra.**

Sau khi Phase 1 test ổn → chuyển Phase 2.

**Phase 5 — ScenePlanner 2.0 đã hoàn thành.**

Kết quả: ScenePlanner nhận `CreativePlan + SubjectLock`, gọi LLM đúng một lần
cho toàn bộ scene plan, trả về `CreativeScene[]` có cấu trúc đầy đủ và kiểm tra
consistency contract trước khi cho scene đi tiếp.

**Phase tiếp theo: Phase 6 — ShotPlanner.**

**Phase 6 — ShotPlanner đã hoàn thành.**

ShotPlanner đã được tách khỏi ScenePlanner và chịu trách nhiệm chi tiết hóa
cách quay từng scene thành các shot cụ thể.

Đã kiểm thử toàn bộ suite: **41 tests passed**.

Phase tiếp theo: **Phase 7 — PromptComposer 2.0**.
done
