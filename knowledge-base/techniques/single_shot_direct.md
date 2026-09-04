# Technique: Single-Shot Direct

## Bản chất
Không chia scene, không storyboard, không chaining. 1 ảnh → 1 video. Dùng cho
trường hợp đơn giản nhất để tránh over-engineer và tốn quota không cần thiết.

## Chỉ dùng khi
- `scene_count == 1` (kịch bản/yêu cầu chỉ cần 1 cảnh ngắn, không có mạch
  chuyện nhiều đoạn)

## Quy trình

1. Nếu có nhân vật/sản phẩm cụ thể cần giữ đúng ngoại hình → vẫn nên chạy
   character-lock trước (tạo 1 ảnh chất lượng cao thay vì dùng thẳng ảnh mẫu
   thấp chất lượng).
2. Sinh prompt ảnh (nếu cần ảnh mới) hoặc dùng thẳng character_sheet_image:

```
{mô tả chủ thể + hành động + bối cảnh}, style: {style}, {lighting/mood}.
```

3. Sinh prompt video:

```
{mô tả chuyển động, camera move, mood}, duration {X}s.
Audio: {mô tả nếu cần}.
```

4. Gọi engine 1 lần: image-to-video.

## Ưu / Nhược
| | |
|---|---|
| Ưu | Nhanh nhất, tốn ít quota nhất, đơn giản nhất để debug |
| Nhược | Không hợp cho video có mạch chuyện/nhiều cảnh |

## Machine-readable summary
```yaml
technique_id: single_shot_direct
requires_engine_capability: []
scene_count: 1
quota_cost: "lowest (1 image call + 1 video call total)"
consistency_risk: "none (single scene, no cross-scene consistency needed)"
depends_on: [character_lock (optional)]
```
