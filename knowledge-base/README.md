# Knowledge Base — AI Video Content Tool

## Mục đích
Đây là lớp "tri thức" đứng giữa input (text kịch bản + ảnh mẫu) và lớp thực thi
(gọi API/automation lên các engine tạo ảnh/video). Lớp này quyết định:
1. Chia kịch bản thành bao nhiêu scene
2. Chọn **kỹ thuật (technique)** nào để sinh video, dựa theo engine đang dùng
3. Sinh đúng **prompt theo cú pháp** mà engine đó hiểu tốt nhất

## Cấu trúc

```
knowledge-base/
├── README.md              ← file này
├── router.md               ← LOGIC CHỌN: input + engine → technique nào
├── character-lock.md        ← bước nền dùng chung mọi nhánh (giữ nhân vật nhất quán)
├── techniques/              ← các CHIẾN THUẬT, độc lập với engine
│   ├── storyboard_sheet.md
│   ├── frame_to_frame_chain.md
│   ├── single_shot_direct.md
│   └── scene_extend_edit.md
└── engines/                 ← NĂNG LỰC & GIỚI HẠN từng engine (dạng profile)
    ├── omni_flash.md
    ├── agnes_ai.md
    └── _template.md         ← copy file này khi thêm engine mới (Veo, Seedance...)
```

## Cách dùng khi tích hợp code (bạn cung cấp endpoint sau)

1. Đọc `router.md` → dựa vào input (số scene cần, engine được chọn, có nhân vật
   lặp lại không, có cần tiết kiệm quota không) → trả về tên 1 technique.
2. Đọc file `techniques/<tên>.md` tương ứng → lấy template prompt.
3. Đọc file `engines/<tên_engine>.md` → lấy syntax riêng, giới hạn, cách gọi.
4. Compose: template prompt (bước 2) + dữ liệu scene thực tế + syntax engine (bước 3)
   → prompt cuối → gửi qua endpoint.

Mỗi file `.md` trong `techniques/` và `engines/` đều có block cuối cùng
**`## Machine-readable summary`** ở dạng YAML/JSON nhỏ — dùng để code parse trực
tiếp, không cần LLM đọc lại toàn bộ markdown mỗi lần.
