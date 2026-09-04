# AI Video Content Tool (Agnes AI, chạy local)

Công cụ tự động: kịch bản văn bản (+ ảnh mẫu tuỳ chọn) → video hoàn chỉnh,
dựa trên Agnes AI (`agnes-2.5-flash`, `agnes-image-2.1-flash`,
`agnes-video-v2.0`). Kiến trúc theo Clean Architecture + SOLID, map đúng
`knowledge-base/software-design.md` đã thiết kế trước đó.

## Cấu trúc thư mục

```
ai_video_tool/
├── app.py                     # launcher giao diện Web (python app.py)
├── main.py                    # CLI entrypoint (thay thế)
├── config.py                  # đọc .env, cấu hình tập trung
├── server/
│   ├── app.py                 # FastAPI: route, WebSocket log stream
│   └── job_manager.py         # quản lý job chạy nền, pub-sub log real-time
├── static/
│   └── index.html             # giao diện control panel (1 file, tự chứa)
├── core/
│   ├── scene_planner.py       # chia kịch bản -> scene[]
│   ├── vision_analyzer.py     # phân tích ảnh mẫu (character-lock)
│   ├── router.py              # logic chọn technique (đúng router.md)
│   └── prompt_composer.py     # template prompt từng technique
├── engines/
│   ├── base_engine.py         # interface chung (Dependency Inversion)
│   └── agnes_client.py        # implement cho Agnes AI thật
├── techniques/                # Strategy Pattern — 1 class / 1 kỹ thuật
│   ├── character_lock.py
│   ├── single_shot_direct.py
│   ├── keyframe_array.py      # ★ mặc định tiết kiệm quota cho Agnes
│   └── frame_to_frame_chain.py
├── orchestrator/
│   ├── task_queue.py          # song song có giới hạn concurrency
│   ├── polling_worker.py      # poll bất đồng bộ nhiều video_id
│   └── pipeline_runner.py     # nhạc trưởng chính, 4 bước
└── utils/
    ├── key_rotation.py        # xoay nhiều API key (round-robin)
    ├── ffmpeg_utils.py        # trích frame cuối + ghép video
    └── logger.py
```

> Ghi chú: `storyboard_sheet` và `scene_extend_edit` được giữ chỗ trong
> `router.py` (đúng luật gốc) nhưng CHƯA implement class kỹ thuật, vì Agnes
> AI hiện không hỗ trợ 2 khả năng đó (`supports_storyboard_read=False`,
> `supports_edit=False`) — router sẽ tự fallback về `frame_to_frame_chain`.
> Khi thêm engine khác (VD: Omni Flash, hỗ trợ cả 2), chỉ cần viết thêm
> `techniques/storyboard_sheet.py` + `techniques/scene_extend_edit.py` theo
> đúng interface `BaseTechnique`, không phải sửa `pipeline_runner.py`.

## Cài đặt

1. Cần **Python 3.10+** và **ffmpeg** đã cài trong PATH:
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   # macOS
   brew install ffmpeg
   ```

2. Cài thư viện Python:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` thành `.env`, điền API key thật:
   ```bash
   cp .env.example .env
   ```
   Muốn bật key rotation (xoay nhiều key khi bị rate-limit), điền nhiều key
   cách nhau dấu phẩy trong `AGNES_API_KEYS`.

## Chạy — Giao diện Web (khuyến nghị)

```bash
python app.py
```

Mở trình duyệt tới **http://127.0.0.1:8420** — giao diện có:

- **Bước 1** — dán kịch bản, chọn style, đặt tên chủ thể chính
- **Bước 2** — toggle "giữ nhân vật nhất quán" (bật lên hiện thêm ô nhập URL ảnh mẫu)
- **Bước 3** — radio "Tiết kiệm" (keyframe_array, mặc định) hoặc "Bình thường" (frame_to_frame_chain)
- **Bước 4** — bấm "Bắt đầu tạo video" — log tiến trình hiện real-time bên phải (qua WebSocket), xong thì video hiện luôn để xem/tải

Không cần mở terminal riêng để theo dõi tiến độ, không cần gõ lệnh CLI mỗi lần chạy.

## Chạy — CLI (thay thế, khi cần tự động hoá/script hoá)

```bash
python main.py \
  --script script.txt \
  --style "cinematic, warm lighting, photographic" \
  --subject "cô gái tóc dài áo dài trắng" \
  --reference https://example.com/anh-mau.jpg \
  --keep-character \
  --quota-mode tiet_kiem
```

Nếu video không có nhân vật cố định xuyên suốt, bỏ `--keep-character` và
`--reference`.

Tham số:
| Flag | Ý nghĩa |
|---|---|
| `--script` | đường dẫn file `.txt` kịch bản, hoặc `-` để nhập qua stdin |
| `--style` | style chung toàn video (chèn vào mọi prompt) |
| `--subject` | tên/mô tả ngắn chủ thể chính |
| `--reference` | URL public (hoặc data URI) ảnh mẫu — **bắt buộc** nếu bật `--keep-character` |
| `--keep-character` | bật character-lock, giữ nhân vật nhất quán xuyên suốt |
| `--quota-mode` | `tiet_kiem` (mặc định, ít request nhất) hoặc `binh_thuong` (kiểm soát kỹ từng scene) |
| `--output` | thư mục lưu kết quả (mặc định `./output`, đổi được qua `.env`) |

## Kết quả

Video cuối nằm ở `output/keyframe_array_final.mp4` (nếu router chọn
`keyframe_array`) hoặc `output/frame_to_frame_final.mp4` (nếu
`frame_to_frame_chain`), kèm các file trung gian (ảnh keyframe, frame cuối
từng scene) để debug khi cần.

## Lưu ý quan trọng

- **Ảnh input phải là URL public HTTPS hoặc data URI base64** — theo đúng
  giới hạn của Agnes API (`engines/agnes_ai.md`).
- Giá hiện tại của Agnes AI ghi là `$0/unit` nhưng có thể là khuyến mãi tạm
  thời — theo dõi lại trước khi build ở quy mô lớn.
- `num_frames` tự động được ép về đúng luật `8n+1` (tối đa 441) trong
  `engines/agnes_client.py::nearest_valid_num_frames`.
- Lỗi video (status `failed`) **không tự động retry** (đúng thiết kế gốc, vì
  video tốn quota hơn ảnh) — cần chạy lại thủ công.

## Cooldown thích ứng (vì server Agnes đang free, không giới hạn cứng)

Vì Agnes hiện free — nghĩa là không có trần "quota" rõ ràng, giới hạn thật sự
là **server chịu tải khi bị bắn request dồn dập**. Nên `utils/key_rotation.py`
tự áp 1 khoảng nghỉ (cooldown) TỐI THIỂU giữa 2 lần **generate ảnh/video**
liên tiếp trên cùng 1 key:

- Mặc định nghỉ **3 phút** (`COOLDOWN_BASE_SEC=180`) trước khi generate tiếp.
- Nếu vẫn dính lỗi/429/503 → **tự tăng thêm 1 phút mỗi lần lỗi**
  (`COOLDOWN_STEP_SEC=60`), tối đa **15 phút** (`COOLDOWN_MAX_SEC=900`).
- Khi ổn định lại (3 lần generate liên tiếp thành công) → **tự giảm dần**
  cooldown về lại mức nền 3 phút.
- Riêng bước **poll trạng thái video** (endpoint nhẹ, không tốn tài nguyên
  như generate) KHÔNG bị áp cooldown này — vẫn check mỗi `POLL_INTERVAL_SEC`
  giây (mặc định 4s) như bình thường, để tiến độ vẫn cập nhật real-time.
- `MAX_CONCURRENT_IMAGE_REQUESTS` / `MAX_CONCURRENT_VIDEO_SUBMIT` mặc định
  đã đổi về **1** (không song song), để không dồn tải thêm lên server free.

Muốn chỉnh tay, sửa trong `.env`:
```
COOLDOWN_BASE_SEC=180
COOLDOWN_MAX_SEC=900
COOLDOWN_STEP_SEC=60
COOLDOWN_DECAY_AFTER_SUCCESS=3
```

Nếu có nhiều API key (`AGNES_API_KEYS=key1,key2,...`), trong lúc key A đang
nghỉ, key B vẫn dùng được ngay — giúp pipeline không đứng khựng hoàn toàn.
"# Nghich_Tiep_Video" 
