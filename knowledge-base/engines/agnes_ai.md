# Engine: Agnes AI

## ⚠️ Trạng thái tri thức
Đã xác minh từ docs chính thức (wiki.agnes-ai.com), tính đến thời điểm build
tri thức này. Giá hiện tại `$0/unit` cho cả 3 model (video/ảnh/text) —
nhưng đây ghi là "Current Price" khác "Standard Price" ($0.005/s video,
$0.003/ảnh, $0.03-0.15/1M token) → **có thể đây là giai đoạn khuyến mãi/free
tạm thời, không phải free vĩnh viễn**. Cần theo dõi lại giá định kỳ.
Base URL chung: `https://apihub.agnes-ai.com`.

Agnes thực chất là **3 model riêng biệt**, không phải 1 model làm mọi việc:

| Model | Việc | Endpoint |
|---|---|---|
| `agnes-2.5-flash` | LLM văn bản + hiểu ảnh (vision) | `/v1/chat/completions` hoặc `/v1/responses` |
| `agnes-image-2.1-flash` | Tạo ảnh (text-to-image, image-to-image) | `/v1/images/generations` |
| `agnes-video-v2.0` | Tạo video (text/image/keyframe-to-video) | `/v1/videos` (async) |

## agnes-2.5-flash — Vision Analyzer dùng model này
- OpenAI-compatible Chat Completions, `messages[].content` nhận mảng gồm
  `text` + `image_url` → dùng đúng cho bước Vision Analyzer (đọc ảnh mẫu chất
  lượng thấp để trích đặc điểm) thay vì phải gọi engine ngoài.
- Hỗ trợ tool calling, streaming, thinking mode (`chat_template_kwargs.enable_thinking`
  hoặc `thinking.budget_tokens` kiểu Anthropic).
- Context window 512K, output tối đa 65.5K token.

## agnes-image-2.1-flash — Sinh ảnh (character sheet, storyboard, scene)
- Text-to-image: cần `model`, `prompt`, `size` (`1K`/`2K`/`3K`/`4K`) + `ratio`
  (`1:1`,`3:4`,`4:3`,`16:9`,`9:16`,`2:3`,`3:2`,`21:9`).
- Image-to-image: thêm `extra_body.image: [url_hoặc_base64]` — dùng để giữ
  bố cục gốc khi chỉnh sửa (đúng nhu cầu "giữ nhân vật, đổi bối cảnh").
- Output: `extra_body.response_format` = `"url"` hoặc `"b64_json"` (đặt
  trong `extra_body`, KHÔNG đặt ở top-level — lỗi thường gặp).
- Tối ưu cho ảnh nhiều chi tiết/bố cục phức tạp → hợp để tạo
  **character sheet nhiều góc** và **storyboard grid nhiều panel** trong 1 ảnh.

## agnes-video-v2.0 — Tạo video (đây là chỗ thay đổi lớn nhất so với giả định cũ)
- **API bất đồng bộ**: `POST /v1/videos` tạo task → poll `GET /agnesapi?video_id=...`
  cho tới khi `status == "completed"`, lấy video tại `metadata.url`.
- Có **3 mode**, KHÔNG chỉ frame-to-frame đơn thuần như giả định ban đầu:
  1. `text-to-video` (mặc định, không cần ảnh)
  2. `image-to-video` (`ti2vid`) — 1 ảnh + prompt mô tả chuyển động
  3. **`keyframes`** — nhận **MẢNG nhiều ảnh** (`extra_body.image: [url1, url2,...]`,
     `extra_body.mode: "keyframes"`) → model tự tạo chuyển động chuyển tiếp
     mượt giữa các keyframe.
- Thời lượng kiểm soát qua `num_frames` (≤441, theo luật `8n+1`) và
  `frame_rate` (1-60): `seconds = num_frames / frame_rate`. Mốc tham khảo:
  81 frame/24fps ≈ 3s, 121/24 ≈ 5s, 241/24 ≈ 10s, 441/24 ≈ 18s (tối đa).
- Có `negative_prompt` và `seed` (reproducibility).
- **KHÔNG thấy tài liệu nào nói tới tính năng edit video đã tạo bằng prompt**
  (khác Omni Flash) → xác nhận giả định cũ: `supports_edit: false`.
- Không thấy đề cập audio đồng bộ sinh kèm video → giả định `supports_audio_output: false`,
  cần ghép nhạc/audio riêng ngoài pipeline (ffmpeg).

## ⚡ Cập nhật quan trọng cho Router: `keyframes` mode = 1 dạng storyboard riêng
Mode `keyframes` của Agnes **không giống hệt** `storyboard_sheet` (1 ảnh lưới
nhiều panel) trong Knowledge Base hiện tại — nó nhận **nhiều ảnh rời** làm
input, để model tự nội suy chuyển động nối giữa chúng. Coi đây là 1 biến thể
mới: `keyframe_array` (xem `techniques/keyframe_array.md`). Ưu điểm so với
`frame_to_frame_chain` thuần: **1 lần gọi API duy nhất** cho ra cả đoạn
chuyển tiếp giữa nhiều keyframe, thay vì N lần gọi rời rạc từng scene.

## Machine-readable summary
```yaml
engine_id: agnes_ai
status: verified   # đã xác minh từ docs chính thức
free: "promotional (current price $0, standard price is paid — monitor for change)"
sub_models:
  vision_llm: agnes-2.5-flash
  image_gen: agnes-image-2.1-flash
  video_gen: agnes-video-v2.0
capabilities:
  supports_storyboard_read: false      # không tài liệu nào xác nhận đọc lưới nhiều panel trong 1 ảnh
  supports_keyframe_array: true        # ĐÃ XÁC NHẬN — mode "keyframes", input nhiều ảnh
  supports_edit: false                 # không tài liệu nào xác nhận edit video có sẵn
  supports_image_to_video: true
  supports_text_to_video: true
  supports_vision_understanding: true  # qua agnes-2.5-flash, dùng cho Vision Analyzer
  supports_audio_output: false         # không đề cập, giả định cần ghép ngoài
  supports_audio_input_for_sync: false
  max_clip_duration_sec: 18            # 441 frames / 24fps
  min_clip_duration_sec: 1
  api_style: "asynchronous task (create + poll)"
limitations:
  - "video generation is async — requires polling loop with backoff"
  - "num_frames must satisfy 8n+1 rule, max 441"
  - "image inputs must be public HTTPS URL or Data URI base64"
  - "current $0 pricing may be promotional, not guaranteed permanent"
recommended_techniques: [keyframe_array, frame_to_frame_chain, single_shot_direct]
