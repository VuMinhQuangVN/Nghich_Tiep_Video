3. Nhưng có một vấn đề lớn tôi phát hiện
   🔴 Phase 6 + Phase 7 đang tồn tại nhưng chưa thực sự đi vào generation pipeline

Đây mới là điểm tôi quan tâm nhất.

Ông đã có:

core/shot_planner.py
models/shot_plan.py

và:

core/prompt_composer.py

Nhưng PipelineRunner hiện tại chạy:

CreativePlan
↓
ScenePlanner
↓
Router
↓
Technique
↓
Agnes

Nó không chạy:

Scene
↓
ShotPlanner
↓
CreativeShot
↓
PromptComposer
↓
final generation prompt

Tôi kiểm tra các technique:

keyframe_array.py
frame_to_frame_chain.py
single_shot_direct.py

chúng vẫn đang sử dụng các helper cũ như:

keyframe_image_prompt(...)
keyframe_video_prompt(...)
scene_image_prompt(...)
scene_video_prompt(...)
single_shot_video_prompt(...)

chứ chưa gọi:

ShotPlanner
PromptComposer
Nghĩa là:

Phase 6:

đã implement

Phase 7:

đã implement

nhưng:

⚠️ chưa được wiring vào đường chạy video thật.

Đây là khác biệt rất quan trọng.

4. Điều này không có nghĩa Phase 6/7 làm sai

Thực ra xét theo cách chia phase ban đầu thì việc này có lý do.

Ông đã cố giữ:

Phase 5
ScenePlanner

rồi:

Phase 6
ShotPlanner

rồi:

Phase 7
PromptComposer

sau đó mới:

Phase 10
Generation Integration

Nên việc chưa wiring toàn bộ vào generation trước Phase 10 là hợp lý.

Nhưng bây giờ Phase 10 đã xong, nên tôi đánh dấu:

🔴 Phase 10 integration chưa hoàn thiện đến mức tận dụng hết Phase 6 + 7.

Đây sẽ là việc đầu tiên tôi muốn xử lý nếu tiếp tục nâng cấp.

5. Một điểm nữa: Phase 11 mới là "boundary", chưa thực sự dùng hết

VideoPostProcessor hiện hỗ trợ:

voiceover
background music
SRT subtitle
text overlay
CTA

Cái này code có thật.

Nhưng trong creative flow:

VideoPostProcessor().process(
result.final_video_path,
postprocessed_path
)

không truyền PostProcessOptions.

Tức là thực tế đang chạy:

Generated Video
↓
VideoPostProcessor
↓
copy nguyên video

chứ chưa phải:

Generated Video
↓
Voiceover
Subtitle
CTA
Music
Text
↓
Final Video
Tôi đánh giá:

🟢 Phase 11 implementation: Có

🟡 Phase 11 user-facing workflow: Chưa hoàn chỉnh

Nhưng điều này đúng với phạm vi ông đã ghi: chưa có AI/TTS/music generation.

6. Phase 10 Simple Mode vẫn còn thiếu Upload Image

Roadmap ban đầu nói:

Ảnh sản phẩm hoặc URL ảnh public

Nhưng hiện API:

product_reference_url: str

và UI:

Product Image / URL

thực tế đang là URL.

Không có:

multipart upload

để người dùng chọn:

shoe.jpg
lipstick.png
product.webp

rồi đưa ảnh local vào pipeline.

Vì vậy:

🟡 URL: OK

🔴 Upload ảnh local: chưa có.

7. Multiple Product Reference cũng chưa đi xuyên pipeline

Data model Phase 1 đã rất tốt:

product_reference_urls: list[str]

Phase 2 cũng hỗ trợ nhiều reference.

SubjectLock cũng có:

reference_urls: list[str]

Nhưng Phase 10 adapter:

product_reference_url=creative_plan.input.product_reference_urls[0]

chỉ lấy:

reference đầu tiên

Các technique cũng nhận:

product_reference_url

là một URL.

=> Về mặt kiến trúc:

Multiple references
↓
Creative layer
↓
SubjectLock

đã hỗ trợ.

Nhưng:

SubjectLock
↓
Generation

chưa truyền toàn bộ references.

Đây cũng là một điểm cần nâng sau này.

8. Phase 12 tôi đánh giá khá ổn, nhưng cần hiểu đúng

Ông có:

platform_optimizer.py

và 4 platform:

TikTok
Instagram Reels
YouTube Shorts
Facebook

Có:

hook
pacing
text
CTA
shot duration
story structure

và cả CreativeDirector + ScenePlanner đều nhận platform guidance.

Đặc biệt TikTok có:

0-3s
3-20s
20-27s
27-30s

=> đúng hướng roadmap.

Nhưng đây vẫn là:

Platform rules
↓
LLM prompt
↓
LLM tự quyết định

chứ chưa phải:

Platform
↓
deterministic validator
↓
bắt buộc scene 0-3s phải hook
↓
CTA nằm cuối

Tôi không coi đây là bug. Chỉ là mức độ hiện tại là optimization guidance, chưa phải hard constraint.

(Phase 12 hiện tại = AI được “dẫn đường”.
Hard validator sau này = AI được “chặn đường sai”.) 9. Tôi phát hiện README đang lỗi thời

Đây là việc nên sửa.

README hiện vẫn mô tả hệ thống cũ kiểu:

Bước 1 — dán kịch bản
Bước 2 — giữ character
Bước 3 — quota
Bước 4 — tạo video

Trong khi code hiện tại đã có:

Simple Mode
Product
Goal
Platform
Duration

↓
ProductAnalyzer
↓
CreativeDirector
↓
CreativePlan
↓
SubjectLock
↓
ScenePlanner
...

README cũng chưa phản ánh đầy đủ:

core/creative_director.py
core/product_analyzer.py
core/platform_optimizer.py
core/shot_planner.py
models/creative_plan.py
models/shot_plan.py
models/subject_lock.py
orchestrator/creative_pipeline_adapter.py
utils/video_post_processor.py
Tôi xếp:

🟡 Documentation debt.

Không ảnh hưởng runtime nhưng nên sửa trước khi coi project là một milestone hoàn chỉnh.

10. Git hiện tại cũng có một chút việc phải dọn

Trong repo:

HEAD:
c17d40e

nhưng working tree có:

M .gitignore
M Qua_Trinh_Nang_Cap.md
M README.md

Tức là 3 file đang modified nhưng chưa commit.

Không phải bug.

Nhưng nếu ông định chốt:

Phase 1 → 12 COMPLETE

thì nên commit 3 file này.

11. Một vấn đề bảo mật nhỏ nhưng tôi phải nhắc

Trong ZIP ông gửi có:

.env

May là:

AGNES_API_KEYS=

hiện đang rỗng nên tôi không thấy API key thật bị đóng gói trong file này.

Git cũng đang ignore:

.env
.env.\*
!.env.example

=> phần này hiện tại ổn.

Nhưng tuyệt đối đừng zip project khi .env đang chứa API key thật.

12. Có một điểm nữa về test

86 test xanh là rất tốt.

Nhưng test hiện tại chủ yếu là:

unit test

- mock engine
- contract test

Chưa phải:

User
↓
HTTP
↓
ProductAnalyzer
↓
Gemini/Agnes thật
↓
CreativeDirector
↓
ScenePlanner
↓
ShotPlanner
↓
PromptComposer
↓
Router
↓
Technique
↓
Video API thật
↓
FFmpeg
↓
Final MP4

Tôi không coi đây là thiếu sót nghiêm trọng, vì gọi API thật trong unit test là không nên.

Nhưng trước khi release thật, chúng ta cần một:

E2E / smoke test

để chứng minh toàn bộ pipeline chạy được với Agnes thật.

13. Kiến trúc hiện tại tôi chấm thế này
    USER
    │
    ▼
    ┌──────────────┐
    │ Simple Mode │
    └──────┬───────┘
    │
    ▼
    Product Analyzer
    │
    ▼
    Creative Director
    │
    ▼
    CreativePlan
    │
    ▼
    Subject Lock
    │
    ▼
    Scene Planner
    │
    ▼
    Shot Planner
    │
    ▼
    Prompt Composer
    │
    ▼
    Router
    │
    ▼
    Technique
    │
    ▼
    Agnes
    │
    ▼
    Video Result
    │
    ▼
    Post Processor
    │
    ▼
    FINAL MP4

Về thiết kế: rất ổn.

Về code hiện tại: phần trên ScenePlanner và phần generation đã có đầy đủ các module, nhưng ShotPlanner → PromptComposer chưa thực sự nằm trên đường chạy production.

Đó là điểm tôi sẽ ưu tiên sửa.

Kết luận Tech Lead

Nếu ông hỏi tôi:

"Tôi có làm xong Phase 1 → 12 chưa?"

Tôi trả lời:

🟢 Có — về milestone implementation: DONE.
Phase 01 ✅
Phase 02 ✅
Phase 03 ✅
Phase 04 ✅
Phase 05 ✅
Phase 06 ✅
Phase 07 ✅
Phase 08 ✅
Phase 09 ✅
Phase 10 ✅*
Phase 11 ✅*
Phase 12 ✅

- = implementation có, nhưng integration còn khoảng trống.

Nhưng nếu hỏi:

"Giờ hệ thống đã hoàn thiện đúng tầm nhìn ban đầu chưa?"

Thì:

🟡 Chưa.

Ba việc tôi muốn chốt trước khi mở feature mới:

1. 🔴 Wiring Phase 6 + 7 vào Generation Pipeline

Scene
↓
ShotPlanner
↓
PromptComposer
↓
Technique
↓
Agnes

2. 🟡 Hoàn thiện Phase 11 flow

Cho phép CreativePlan → post-processing options → final video thực sự sử dụng subtitle/CTA/voice/music khi có input.

3. 🟡 Dọn documentation + commit

README phải phản ánh đúng kiến trúc hiện tại.

📌 Vậy 2 mục trong audit hiện tại
Vấn đề Trạng thái
🔴 Phase 6/7 chưa vào generation pipeline ✅ Đã giải quyết
🟡 Phase 11 chỉ là boundary ✅ Đã giải quyết flow
AI/TTS tự sinh voice ⏳ Chưa làm
AI tự sinh background music ⏳ Chưa làm
Mỗi CreativeShot thành một video clip riêng ⚠️ Chưa làm
Multiple product refs truyền hết xuống generation ⏳ Chưa làm
Local product image upload ⏳ Chưa làm
Platform optimization enforcement cứng ⏳ Chưa làm
README cập nhật ⏳ Chưa làm
Real Agnes E2E test ⏳ Chưa làm
Một lưu ý quan trọng

Phase 6/7 đã được wiring, nhưng hiện tại CreativeShot vẫn được gom thành prompt sequence trong phạm vi một Scene.

Thứ tự tôi chốt
✅ Phase 6/7 wiring
✅ Phase 11 post-processing flow
│
▼
🔴 NOW #1
Local Product Image Upload
│
▼
🔴 NOW #2
Multiple Product References → Generation
│
▼
🟡 Sau đó
Generated Video
↓
Voiceover
Subtitle
CTA
Music
Text
↓
Final Video

Và tôi không đụng vào vấn đề "mỗi CreativeShot tạo một clip riêng" ở bước này. Cái đó cũng nên tách thành một task riêng để tránh làm Phase 10 phình quá mức.
