# Character / Style Sheet Lock

## Khi nào dùng
Bất cứ khi nào có nhân vật, sản phẩm, hoặc bối cảnh đặc trưng xuất hiện lại ở
từ 2 scene trở lên. Đây KHÔNG phải 1 technique độc lập — là bước chuẩn bị bắt
buộc chạy TRƯỚC khi vào router chọn technique chính.

## Vì sao bắt buộc
Pipeline nào bỏ qua bước này sẽ gặp hiện tượng "trôi" (drift): nhân vật đổi
mặt, đổi trang phục, đổi tông màu giữa các scene — lỗi phổ biến nhất khi
generate từng ảnh/video rời rạc mà không khoá nhân vật trước.

## Cách làm

1. Lấy ảnh mẫu đầu vào (chất lượng thấp, chỉ dùng để PHÂN TÍCH — không dùng
   trực tiếp làm nguồn video).
2. Vision Analyzer trích đặc điểm: khuôn mặt/hình dạng, trang phục, tỉ lệ,
   tông màu, phong cách (ảnh thật / 3D / anime...).
3. Sinh prompt tạo **character sheet**: yêu cầu AI tạo ảnh (Nano Banana hoặc
   tương đương) ra 1 ảnh chứa nhiều góc nhìn cùng 1 nhân vật/sản phẩm:
   - Góc trước, góc nghiêng trái, góc nghiêng phải, góc sau
   - 1 ảnh cận mặt/chi tiết (nếu là nhân vật hoặc sản phẩm có chi tiết quan trọng)
4. Ảnh character sheet này = `character_sheet_image`, được **tái sử dụng làm
   ảnh tham chiếu (reference/ingredient) cho MỌI scene** trong cùng 1 video,
   bất kể sau đó dùng technique nào (storyboard_sheet hay frame_to_frame_chain).

## Prompt template sinh character sheet

```
Character reference sheet, [X] turnaround angles: front view, 3/4 left,
3/4 right, back view[, close-up on face/key detail].
Subject: {mô tả chủ thể trích từ Vision Analyzer}.
Style: {phong cách trích từ ảnh mẫu — photographic / 3D render / anime / v.v.}.
Consistent lighting, neutral background, same subject across all angles,
high detail, production-ready reference sheet.
```

## Lưu ý quan trọng
- Chỉ cần chạy bước này **1 LẦN cho mỗi nhân vật/sản phẩm**, không phải 1 lần
  mỗi scene — đây chính là chỗ tiết kiệm quota.
- Nếu video có nhiều nhân vật xuất hiện cùng lúc, cân nhắc tạo character
  sheet riêng cho từng nhân vật rồi ghép mô tả lại trong prompt scene, thay
  vì nhồi tất cả vào 1 ảnh sheet duy nhất (dễ gây nhầm lẫn đặc điểm).

## Machine-readable summary
```yaml
step_id: character_lock
required_when: "has_recurring_character == true"
frequency: "once per unique subject (not per scene)"
input:
  - low_quality_reference_image (analysis only, not used as video source)
output:
  - character_sheet_image (high quality, used as reference across all scenes)
reused_by_techniques: [storyboard_sheet, frame_to_frame_chain, single_shot_direct, scene_extend_edit]
```
