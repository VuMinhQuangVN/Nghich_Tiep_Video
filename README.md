# AI Video Content Tool — Creative Brain + Agnes

Công cụ local để tạo video quảng cáo sản phẩm theo flow:

```text
Ảnh sản phẩm / style reference
        ↓
🧠 Creative Brain
        ↓
5 kịch bản khác nhau
        ↓
Người dùng chọn 1
        ↓
🖼️ Gen storyboard cho từng cảnh
        ↓
🎬 Gen video từ storyboard
        ↓
✂️ Trim theo editorial timeline
        ↓
🔗 Concat
        ↓
Final video
```

## Creative Brain

AI phải tạo **đúng 5 candidate** trong một lần brainstorm.

Timeline **không bị hard-code** theo kiểu `15s = 5 cảnh`, `20s = 6 cảnh` hay `30s = N cảnh`.
Các ví dụ 2–4 giây/cảnh và các phép chia như `3+3+3+3+3` chỉ là gợi ý để AI hiểu nhịp short-form.

AI tự quyết:
- số lượng cảnh;
- thời lượng từng cảnh;
- hook, product reveal, demo/benefit, proof/result, CTA;
- cấu trúc kể chuyện phù hợp với sản phẩm.

Tổng thời lượng editorial của candidate phải đúng duration người dùng yêu cầu.

## Production pipeline

Chỉ candidate được người dùng chọn mới tiêu tốn request render.

Mỗi cảnh:

1. Gen một storyboard image bằng `agnes-image-2.5-flash`.
2. Gửi storyboard image sang `agnes-video-2.5-flash` ở `mode=reference`.
3. Provider có thể phải generate clip 4–12s; hệ thống trim về đúng duration của cảnh.
4. Concat các cảnh đã trim.

Video 2.5 Flash hiện dùng `720P`, `seconds` 4–12 và tối đa 5 reference images theo contract trong `knowledge-base/agnes-video-2.5-flash.md`.

## Logger

- Main UI: log của job hiện tại qua `WS /ws/jobs/{job_id}`.
- Logger riêng: `http://127.0.0.1:8420/logger`.
- Logger riêng giữ history và nhận log realtime qua `WS /ws/logger`.
- Trang chính dùng `Cache-Control: no-store` để tránh browser giữ UI cũ sau update.

## Chạy

```bash
pip install -r requirements.txt
python app.py
```

Mở:

```text
http://127.0.0.1:8420
```

Logger:

```text
http://127.0.0.1:8420/logger
```

## Model mặc định

```text
AGNES_TEXT_MODEL=agnes-2.5-flash
AGNES_IMAGE_MODEL=agnes-image-2.5-flash
AGNES_VIDEO_MODEL=agnes-video-2.5-flash
AGNES_VIDEO_EXPERIMENTAL_MODEL=agnes-video-v2.0
```

`video-v2.0` là fallback ổn định khi cần.

## Lưu ý

- Không commit `.env`.
- Không đưa `venv`, `.git`, cache hoặc output vào release ZIP.
- Script Mode cũ và lựa chọn request mode đã bị loại khỏi production flow.
