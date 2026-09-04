# Technique: Storyboard Sheet

## Bản chất
Sinh 1 ảnh tổng dạng lưới (grid) chứa nhiều panel, mỗi panel = 1 scene, có
đánh số thứ tự + ghi chú camera/thời gian. Feed ảnh này vào engine 1 lần duy
nhất, kèm prompt mô tả trình tự → engine tự tách và animate liền mạch thành
video multi-scene.

## Chỉ dùng khi
- `engine.supports_storyboard_read == true` (xem `engines/`)
- Số scene từ 2 trở lên
- Ưu tiên tiết kiệm quota (ít request nhất trong các technique)

## Cảnh báo quan trọng
Kỹ thuật này **rủi ro cao nếu engine yếu khả năng đọc hiểu bố cục phức tạp**.
Đã ghi nhận trường hợp: dùng 1 ảnh + prompt trực tiếp tạo video thất bại 5
lần liên tiếp (đám đông chuyển động hỗn loạn, camera chuyển cảnh vô lý, mất
liên tục vật cản, hành động sai thời điểm) — cho tới khi đổi sang storyboard
có đánh số panel + mốc thời gian + ghi chú camera rõ ràng thì mới ra đúng
ngay lần đầu. Nghĩa là: storyboard sheet CHỈ hiệu quả khi làm đủ chi tiết
(có số thứ tự, mốc thời gian, ghi chú chuyển động) — sheet sơ sài dễ thất bại
y như cách generate trực tiếp.

## Quy trình

1. Lấy `character_sheet_image` từ bước character-lock (nếu có nhân vật lặp lại).
2. Scene Planning đã chia sẵn N scene, mỗi scene có: mô tả hành động, camera
   move, thời lượng dự kiến.
3. Sinh prompt tạo ảnh storyboard (dùng AI tạo ảnh, tham chiếu
   `character_sheet_image` nếu có):

```
Professional film storyboard sheet, [N] panels in a grid layout, numbered
1 to [N]. Each panel represents one scene in sequence.

Panel 1 [X sec]: {mô tả scene 1: hành động, bối cảnh, camera direction}
Panel 2 [X sec]: {mô tả scene 2}
...
Panel N [X sec]: {mô tả scene N}

Include motion arrows and camera direction notes on each panel.
Consistent character/subject appearance across all panels
(reference: {character_sheet_image nếu có}).
Consistent lighting and color grading across panels.
Style: {style trích từ ảnh mẫu / Vision Analyzer}.
```

4. Sau khi có ảnh storyboard, sinh prompt video:

```
Generate a multi-scene video following this storyboard exactly, in panel
order 1 to [N]. Panel 1 lasts approximately [X]s, panel 2 lasts [X]s, ...
Maintain consistent subject appearance, lighting, and style across all
panel transitions. Camera movement and timing as annotated in each panel.
Audio: {mô tả nhạc nền/âm thanh nếu cần, engine hỗ trợ audio đồng bộ}.
```

5. Gửi ảnh storyboard + prompt video vào engine (1 lần gọi).
6. Nếu 1 đoạn bị lỗi sau khi render → dùng `scene_extend_edit` (nếu engine
   hỗ trợ) thay vì render lại toàn bộ.

## Ưu / Nhược
| | |
|---|---|
| Ưu | Ít request nhất; nhân vật/style nhất quán cao nhất vì sinh cùng lúc |
| Nhược | Phụ thuộc hoàn toàn vào khả năng đọc bố cục của engine; storyboard sơ sài = dễ fail; khó debug nếu 1 panel bị hiểu sai mà không có tính năng edit đi kèm |

## Machine-readable summary
```yaml
technique_id: storyboard_sheet
requires_engine_capability: ["supports_storyboard_read"]
min_scene_count: 2
quota_cost: "low (1 image call + ~1 video call per whole sequence)"
consistency_risk: "low (if storyboard detailed) / high (if storyboard vague)"
depends_on: [character_lock (optional but recommended)]
fallback_if_engine_unsupported: frame_to_frame_chain
```
