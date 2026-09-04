# Thiết kế phần mềm: AI Content Tool (bản Agnes AI trước)

## 1. Nguyên tắc thiết kế UI

- **Không hỏi người dùng những gì hệ thống tự suy ra được.** VD: không cần
  radio "chọn technique" — hệ thống tự chọn theo Router. Người dùng chỉ chọn
  những gì liên quan tới Ý ĐỊNH (bao nhiêu scene, có nhân vật lặp lại không,
  ưu tiên tốc độ hay tiết kiệm quota).
- **Toggle/radio chỉ xuất hiện khi có sự đánh đổi thật (trade-off) mà máy
  không tự quyết được thay người dùng.**
- **Xử lý song song ở đâu an toàn thì làm ngầm, không cần hỏi** — người dùng
  không cần biết ảnh 3 scene được sinh song song hay tuần tự, trừ khi họ
  muốn xem tiến độ real-time.

## 2. Luồng UI (wizard 4 bước)

```
┌─────────────────────────────────────────────────────┐
│ BƯỚC 1: Input                                        │
│  - Ô nhập text kịch bản (textarea)                   │
│  - Upload ảnh mẫu (optional, kéo thả, nhiều ảnh)     │
│  - [Toggle] "Có nhân vật/sản phẩm cần giữ nhất quán  │
│    xuyên suốt?" → Bật thì bắt buộc có ít nhất 1 ảnh  │
│    mẫu ở trên (validate ngay khi bật)                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ BƯỚC 2: Xác nhận kế hoạch (Scene Planning)           │
│  - Hệ thống tự chia scene (gọi agnes-2.5-flash),     │
│    hiển thị danh sách scene dạng card, mỗi card có:  │
│    mô tả, thời lượng dự kiến, camera move             │
│  - [+ Thêm scene] [Xoá] [Kéo thả sắp xếp lại]        │
│  - [Radio] Chế độ quota:                             │
│      ( ) Tiết kiệm request (gộp nhiều scene/lần gọi) │
│      (•) Bình thường (mỗi scene 1 lần gọi, dễ soát)  │
│    → Radio này chỉnh giá trị quota_mode cho Router   │
│  - KHÔNG có ô chọn "technique" — ẩn hoàn toàn khỏi   │
│    người dùng, chỉ hiện ở khu Advanced (xem mục 5)   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ BƯỚC 3: Preview trước khi tốn quota video            │
│  - Hiển thị: character sheet (nếu có) + ảnh từng     │
│    scene/keyframe đã sinh                            │
│  - Mỗi ảnh có nút [Tạo lại ảnh này] (không đụng ảnh  │
│    khác — tiết kiệm quota)                           │
│  - [Nút lớn] "Xác nhận, tạo video" ← CHẶN Ở ĐÂY,     │
│    không tự động chạy tiếp, vì đây là bước tốn quota │
│    video (đắt hơn ảnh)                               │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ BƯỚC 4: Render & Kết quả                             │
│  - Thanh tiến độ song song theo từng scene/video-task │
│    (xem mục 3 — xử lý song song)                     │
│  - Mỗi video-task: [Chờ] [Đang tạo] [Xong ✓] [Lỗi ✗] │
│  - Video lỗi: [Thử lại] hoặc [Sửa prompt rồi thử lại]│
│  - Khi tất cả xong: nút [Ghép nối thành video cuối]   │
│  - Sau ghép: player preview + [Tải về]               │
└─────────────────────────────────────────────────────┘
```

## 3. Xử lý song song (Concurrency Design)

### Nguyên tắc chung
Song song hoá **trong phạm vi 1 lần "duyệt"** của người dùng (không tự động
chạy vượt qua các bước cần xác nhận ở Bước 3), và giới hạn số luồng đồng thời
để tránh vỡ rate-limit của Agnes.

### Sơ đồ song song theo từng bước

```
BƯỚC 2 (Scene Planning): tuần tự — chỉ 1 lệnh gọi LLM (agnes-2.5-flash)
    để phân tích + chia scene toàn bộ kịch bản 1 lần. Không cần song song.

BƯỚC 3 (Sinh ảnh):
    IF character_lock cần chạy:
        → chạy character_sheet TRƯỚC, chờ xong (bắt buộc tuần tự,
          vì mọi ảnh scene sau đều phụ thuộc kết quả này)
    SAU KHI có character_sheet (hoặc không cần):
        → sinh ảnh cho TẤT CẢ scene/keyframe CÙNG LÚC (song song),
          giới hạn concurrency = N (worker pool, mặc định 3-5 luồng
          cùng lúc, để tránh 429 rate-limit)
        → mỗi ảnh độc lập, lỗi 1 ảnh không chặn ảnh khác

BƯỚC 4 (Sinh video), theo technique đã chọn:
    IF technique == keyframe_array:
        → CHỈ 1 request video duy nhất (đã gộp nhiều keyframe),
          không có gì để song song ở bước này, chỉ có polling
          bất đồng bộ (không block UI trong lúc chờ)

    IF technique == frame_to_frame_chain:
        → BẮT BUỘC TUẦN TỰ giữa các scene (scene N cần frame cuối
          của scene N-1 làm input) — đây là điểm KHÔNG song song
          được, phải barrier chờ từng bước
        → Nhưng việc TRÍCH FRAME CUỐI (ffmpeg) và POLLING trạng thái
          có thể chạy nền không chặn UI

    IF technique == storyboard_sheet:
        → chỉ 1 request video duy nhất sau khi có ảnh storyboard,
          không cần song song ở bước video
```

### Cơ chế polling bất đồng bộ (áp dụng agnes-video-v2.0)
Vì API video là async (tạo task → poll kết quả), thiết kế theo pattern
**task queue + polling worker**, không polling đồng bộ chặn luồng chính:

```
1. Submit tất cả video task cần tạo (theo đúng ràng buộc song song/tuần tự
   ở trên) → nhận về danh sách video_id
2. 1 worker nền (interval ~3-5s) poll trạng thái TẤT CẢ video_id đang
   "queued"/"in_progress" cùng lúc (gộp thành ít lần gọi nhất có thể)
3. UI cập nhật trạng thái real-time qua trạng thái poll (không cần
   người dùng bấm refresh)
4. video_id nào "completed" → tải về, đánh dấu xong
   video_id nào "failed" → hiện nút [Thử lại] riêng cho task đó
```

### Giới hạn concurrency đề xuất (điều chỉnh khi biết rate-limit thật)
- Sinh ảnh: tối đa 3-5 request đồng thời
- Submit video task: tối đa 2-3 request đồng thời (vì video nặng hơn, dễ
  chạm rate-limit hơn ảnh)
- Polling: gộp nhiều video_id trong ít lần gọi nhất, không mở luồng poll
  riêng cho từng video

## 4. Toggle/Radio cụ thể trong UI — vì sao chọn kiểu nào

| Control | Vị trí | Vì sao dùng loại này |
|---|---|---|
| Toggle "Giữ nhân vật nhất quán" | Bước 1 | Bật/tắt nhị phân, ảnh hưởng có chạy character-lock hay không — đúng bản chất on/off |
| Radio "Chế độ quota" (Tiết kiệm / Bình thường) | Bước 2 | 2 lựa chọn loại trừ nhau, ảnh hưởng trực tiếp `quota_mode` trong Router — đúng bản chất chọn 1-trong-2 |
| Nút [Tạo lại ảnh này] | Bước 3, trên từng ảnh | Hành động (action), không phải lựa chọn trạng thái — dùng nút, không dùng toggle |
| Nút xác nhận lớn trước khi tạo video | Bước 3 | Cổng chặn (gate) trước bước tốn quota nhất — cố tình KHÔNG tự động để người dùng kiểm soát chi phí |
| KHÔNG có control chọn "technique" ở luồng chính | - | Đây là quyết định kỹ thuật thuộc về Router, hiển thị ra sẽ gây rối cho người dùng không rành kỹ thuật — chỉ lộ ra ở Advanced Mode |

## 5. Advanced Mode (ẩn mặc định, dành cho bạn — người xây tool)

Có 1 khu riêng (VD: nút "⚙ Nâng cao" ẩn ở góc), khi bật ra mới hiện:
- Dropdown chọn **engine** thủ công (mặc định "Tự động" — dùng Agnes; sau
  này thêm Omni Flash/Flow thì đây là chỗ chọn tay hoặc để hệ thống tự động
  luân chuyển tài khoản)
- Hiển thị rõ **technique đã được Router chọn** cho lần chạy này (chỉ để
  xem/debug, không sửa trực tiếp trừ khi thật sự cần ép buộc)
- Số lượng keyframe/scene tối đa cho phép chia (giới hạn an toàn quota)
- Log request/response thô (JSON) để debug khi API lỗi

## 6. Kiến trúc module code (map với UI ở trên)

```
/core
  scene_planner.py     → gọi agnes-2.5-flash, input text+ảnh mẫu, output scene[]
  router.py             → đọc knowledge-base/router.md logic, output technique
  prompt_composer.py    → đọc knowledge-base/techniques/<x>.md + engines/<x>.md,
                           ghép prompt cuối
  vision_analyzer.py    → gọi agnes-2.5-flash (image_url input) phân tích ảnh mẫu

/engines
  agnes_client.py        → wrapper 3 model Agnes (chat/image/video),
                           chứa hàm submit_video_task() + poll_video_task()
  base_engine.py         → interface chung, để sau thêm omni_flash_client.py
                           implement cùng interface

/orchestrator
  task_queue.py          → hàng đợi task, giới hạn concurrency (semaphore)
  polling_worker.py       → 1 vòng lặp nền poll toàn bộ video task đang chờ
  pipeline_runner.py      → điều phối toàn bộ luồng theo Bước 1→4, gọi đúng
                           thứ tự song song/tuần tự theo mục 3

/ui
  step1_input.*
  step2_scene_review.*
  step3_image_preview.*
  step4_render_progress.*
```

## 7. Xử lý lỗi & retry (ngắn gọn, chi tiết hơn để sau khi có endpoint thật)
- Lỗi ảnh: retry tự động 1 lần với cùng prompt trước khi báo người dùng.
- Lỗi video (status `failed`): KHÔNG tự động retry (vì tốn quota hơn ảnh) —
  luôn hỏi người dùng qua nút [Thử lại] ở Bước 4.
- Lỗi 503 (service busy) từ Agnes: dùng exponential backoff cho polling,
  không phải cho việc submit task mới.

## Machine-readable summary
```yaml
ui_flow: [input, scene_review, image_preview_gate, render_progress]
concurrency_rules:
  image_generation: {parallel: true, max_concurrent: 5}
  video_task_submit: {parallel: true, max_concurrent: 3}
  video_polling: {parallel: true, batched: true, interval_sec: 4}
  frame_to_frame_chain: {parallel: false, reason: "each scene depends on previous frame"}
  keyframe_array: {parallel: false, reason: "single API call covers all keyframes"}
hard_gates:
  - "before video generation (Step 3 -> Step 4): explicit user confirmation required"
controls:
  - {id: consistent_character_toggle, type: toggle, step: 1}
  - {id: quota_mode, type: radio, step: 2, options: ["tiết_kiệm", "bình_thường"]}
  - {id: technique_selector, type: hidden, visible_in: advanced_mode_only}
