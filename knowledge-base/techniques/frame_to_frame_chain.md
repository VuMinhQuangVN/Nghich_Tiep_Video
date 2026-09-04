# Technique: Frame-to-Frame Chaining

## Bản chất
Sinh video từng scene một, tuần tự. Khung hình CUỐI của video scene trước
được trích ra làm ảnh ĐẦU vào (anchor) cho scene kế tiếp. Cứ thế nối tiếp cho
đến hết N scene.

```
[Ảnh mẫu/character sheet] → video scene 1 → [frame cuối scene 1]
    → video scene 2 → [frame cuối scene 2]
    → video scene 3 → ... → ghép nối tất cả
```

## Chỉ dùng khi
- Engine KHÔNG hiểu bố cục storyboard đa cảnh (`supports_storyboard_read ==
  false`) — ví dụ Agnes AI. Đây là lựa chọn MẶC ĐỊNH an toàn cho engine loại
  này vì mọi engine image-to-video cơ bản đều làm được, không đòi hỏi khả
  năng "đọc hiểu" phức tạp.
- Hoặc engine hiểu storyboard nhưng không ưu tiên tiết kiệm quota, muốn kiểm
  soát/duyệt kỹ từng scene trước khi sang scene tiếp theo.

## Quy trình

1. Lấy `character_sheet_image` từ character-lock (nếu có nhân vật lặp lại) —
   dùng làm anchor cho SCENE ĐẦU TIÊN.
2. Với mỗi scene i (từ 1 đến N):
   a. Ảnh input = frame cuối của scene (i-1), hoặc character_sheet_image nếu
      i = 1, hoặc ảnh mới sinh riêng nếu scene cần đổi bối cảnh hoàn toàn.
   b. Sinh prompt tạo ảnh (nếu cần ảnh mới thay vì dùng frame cũ):

```
{mô tả bối cảnh/hành động mở đầu scene i}, subject consistent with
reference image, style: {style chung toàn video}, {lighting/mood scene i}.
```

   c. Sinh prompt video cho scene i:

```
{mô tả hành động, camera move, mood của scene i}, duration {X}s.
Maintain exact subject appearance and style from the reference image.
Audio: {mô tả nếu cần}.
```

   d. Gọi engine: image-to-video với ảnh input (bước a) + prompt (bước c).
   e. Trích frame cuối của video vừa tạo → dùng làm input cho scene i+1.
3. Ghép nối tất cả video scene theo thứ tự (ffmpeg hoặc tương đương).

## Kiểm soát "drift" (trôi phong cách qua nhiều scene)
Vì mỗi scene tạo riêng, sai lệch nhỏ có thể tích luỹ dần qua các scene. Giảm
thiểu bằng cách:
- Luôn nhắc lại mô tả style/nhân vật cố định trong MỌI prompt, không chỉ dựa
  vào ảnh anchor.
- Với video dài (>4-5 scene), cân nhắc quay lại đối chiếu với
  `character_sheet_image` gốc mỗi 3 scene một lần (không chỉ nối chain thuần
  tuý) để "kéo" phong cách về gần bản gốc.

## Ưu / Nhược
| | |
|---|---|
| Ưu | Engine nào cũng chạy được kể cả engine cơ bản/free; dễ duyệt và sửa từng đoạn trước khi đi tiếp; lỗi 1 scene không ảnh hưởng ảnh gốc |
| Nhược | Tốn nhiều request hơn storyboard_sheet (mỗi scene ít nhất 1 lần gọi ảnh + 1 lần gọi video); rủi ro trôi phong cách tích luỹ qua nhiều scene nếu không kiểm soát |

## Machine-readable summary
```yaml
technique_id: frame_to_frame_chain
requires_engine_capability: []  # không đòi hỏi gì đặc biệt, hoạt động với mọi engine image-to-video
min_scene_count: 1
quota_cost: "medium-high (roughly 1 image call + 1 video call PER scene)"
consistency_risk: "medium (cumulative drift over many scenes, mitigated by re-anchoring)"
depends_on: [character_lock (optional but recommended)]
default_for_engines_without: ["supports_storyboard_read"]
```
