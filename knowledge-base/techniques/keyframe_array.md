# Technique: Keyframe Array

## Bản chất
Khác với `storyboard_sheet` (1 ảnh lưới nhiều panel) và khác
`frame_to_frame_chain` (N lần gọi API rời rạc), kỹ thuật này gửi **1 mảng
nhiều ảnh rời** (2 ảnh trở lên) vào **1 lần gọi API video duy nhất**, để
engine tự nội suy chuyển động chuyển tiếp mượt giữa các ảnh đó theo đúng thứ
tự trong mảng.

```
[ảnh keyframe 1, ảnh keyframe 2, ảnh keyframe 3, ...] 
    → 1 lần gọi API (mode="keyframes")
    → 1 video liền mạch đi qua tất cả các keyframe theo thứ tự
```

## Chỉ dùng khi
- `engine.supports_keyframe_array == true` (hiện xác nhận có ở Agnes AI,
  `agnes-video-v2.0`, qua `extra_body.mode: "keyframes"`)
- Có từ 2 scene/khoảnh khắc trở lên muốn nối liền mạch
- Muốn tiết kiệm quota hơn `frame_to_frame_chain` (1 request thay vì N) mà
  vẫn không cần engine phải "đọc hiểu" bố cục ảnh lưới phức tạp như
  `storyboard_sheet` đòi hỏi

## Vì sao khác `storyboard_sheet`
`storyboard_sheet` cần engine ĐỌC HIỂU 1 ảnh phức tạp (nhiều panel, chữ ghi
chú, mũi tên...) — rủi ro cao nếu engine yếu phần này. `keyframe_array` chỉ
cần engine nhận NHIỀU ảnh RIÊNG BIỆT rõ ràng và nội suy giữa chúng — không
đòi hỏi khả năng đọc bố cục phức tạp, phù hợp hơn với engine "cơ bản" như
Agnes.

## Quy trình

1. Lấy `character_sheet_image` từ character-lock (nếu có nhân vật lặp lại).
2. Scene Planning đã chia N khoảnh khắc chính (không cần chia quá nhỏ như
   frame_to_frame_chain — mỗi keyframe đại diện 1 "điểm chốt" quan trọng
   trong chuyển động, không phải 1 scene đầy đủ).
3. Với mỗi keyframe cần thiết, sinh ảnh riêng (dùng
   `agnes-image-2.1-flash`, tham chiếu `character_sheet_image` để giữ nhất
   quán qua `extra_body.image`):

```
{mô tả khoảnh khắc keyframe i: tư thế, bối cảnh, ánh sáng}, 
subject consistent with reference image, style: {style chung}.
```

4. Thu thập URL/base64 của tất cả ảnh keyframe theo ĐÚNG thứ tự thời gian.
5. Sinh prompt mô tả chuyển động tổng thể:

```
Generate a smooth cinematic transition through these keyframes in order,
maintaining {tên nhân vật/chủ thể} identity, consistent camera angle logic,
and natural motion between each keyframe. {mô tả tổng thể mood/nhịp điệu}.
```

6. Gọi API video 1 lần:
```json
{
  "model": "agnes-video-v2.0",
  "prompt": "{prompt bước 5}",
  "extra_body": {
    "image": ["url_keyframe_1", "url_keyframe_2", "url_keyframe_3"],
    "mode": "keyframes"
  },
  "num_frames": 241,
  "frame_rate": 24
}
```
7. Poll kết quả (API bất đồng bộ), lấy video tại `metadata.url`.

## Số lượng keyframe khuyến nghị
- 2 keyframe: chuyển tiếp đơn giản (VD: trước/sau 1 hành động)
- 3-4 keyframe: đủ cho 1 đoạn có mở đầu — cao trào — kết, vẫn giữ chất lượng
  nội suy tốt
- Trên 4-5 keyframe: chưa có xác nhận engine xử lý tốt tới đâu — nên test
  thực tế trước khi dùng số lượng lớn, có nguy cơ nội suy kém hoặc bỏ sót ý.

## Ưu / Nhược
| | |
|---|---|
| Ưu | Chỉ 1 request video cho cả chuỗi chuyển động nhiều điểm chốt — tiết kiệm quota hơn hẳn frame_to_frame_chain; không đòi hỏi engine đọc bố cục phức tạp như storyboard_sheet |
| Nhược | Vẫn tốn N request ảnh (mỗi keyframe 1 ảnh) trước khi gọi video; số keyframe tối ưu chưa được xác nhận qua thực nghiệm; ít kiểm soát chi tiết giữa các keyframe hơn cách chia scene tách bạch |

## Machine-readable summary
```yaml
technique_id: keyframe_array
requires_engine_capability: ["supports_keyframe_array"]
min_keyframe_count: 2
recommended_keyframe_count: "3-4"
quota_cost: "medium (N image calls + 1 video call, vs N+N for frame_to_frame_chain)"
consistency_risk: "medium (depends on model's interpolation quality between distant keyframes)"
depends_on: [character_lock (optional but recommended)]
confirmed_on_engines: [agnes_ai]
