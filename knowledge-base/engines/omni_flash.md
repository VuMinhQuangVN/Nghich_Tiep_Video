# Engine: Gemini Omni Flash (Google Flow)

## Trạng thái
Public preview (tính đến thời điểm build tri thức này). API model ID:
`gemini-omni-flash-preview`. Có thể dùng qua Google Flow (web UI), Gemini API,
Google AI Studio. Giá tham khảo ~$0.10/giây video (không phải free) — cần
kiểm tra lại giá/hạn mức thực tế khi tích hợp vì đang preview, dễ thay đổi.

## Năng lực
- Xử lý đồng thời text, ảnh, video làm input (đa phương thức thật, không
  phải ghép nhiều model riêng lẻ).
- Tạo video 4s, 6s, 8s, và **10s** (10s là tính năng riêng của Omni Flash,
  các model Veo khác trong Flow không có).
- **Edit video đã tạo/đã upload bằng prompt tự nhiên**, giữ nguyên phần không
  yêu cầu sửa — dùng cho technique `scene_extend_edit`.
- Audio sinh đồng bộ cùng lúc với video (không cần pipeline TTS/sound riêng),
  có thể prompt cụ thể loại âm thanh mong muốn.
- Có khả năng hiểu ngữ cảnh phức tạp trong ảnh input tốt hơn các model video
  trước đó → đủ điều kiện dùng technique `storyboard_sheet` (đọc hiểu bố cục
  nhiều panel trong 1 ảnh).
- Tạo giọng nói tuỳ chỉnh (custom voice) — chọn giọng có sẵn rồi mô tả cách
  chỉnh/style hoá bằng prompt.

## Giới hạn (quan trọng khi thiết kế fallback)
- **Không nhận audio làm input** để đồng bộ chuyển động theo voiceover có
  sẵn — nếu cần lipsync theo voice thu sẵn, phải xử lý ngoài pipeline này.
- Còn hạn chế về: mở rộng cảnh (scene extension) trong 1 số trường hợp, 1 số
  kiểu tham chiếu video, và tính nhất quán nhân vật khi đổi cảnh mạnh.
- Vì là preview, có ghi nhận model có thể vô tình tạo ra nhân vật giống IP có
  bản quyền nếu prompt khéo → cần review trước khi publish thương mại.
- Một số tính năng (custom voice, edit) chỉ khả dụng ở 1 số quốc gia.

## API cơ bản (tham khảo, cần xác nhận lại field chính xác khi bạn cung cấp endpoint)
```
POST /v1/interactions (hoặc endpoint tương đương Flow cung cấp)
model: "gemini-omni-flash-preview"
input: <prompt text>
image input: qua Files API, upload trước rồi tham chiếu file URI
response_format: { type: "video", aspect_ratio: "9:16" | "16:9" }
```

## Machine-readable summary
```yaml
engine_id: omni_flash
status: public_preview
free: false
pricing_note: "~$0.10/sec video, verify current pricing at integration time"
capabilities:
  supports_storyboard_read: true
  supports_edit: true
  supports_image_to_video: true
  supports_audio_output: true
  supports_audio_input_for_sync: false
  max_clip_duration_sec: 10
  min_clip_duration_sec: 4
limitations:
  - "no audio input for motion sync"
  - "character consistency may degrade on strong scene changes"
  - "risk of IP-similar character generation, review before commercial publish"
recommended_techniques: [storyboard_sheet, scene_extend_edit, frame_to_frame_chain, single_shot_direct]
