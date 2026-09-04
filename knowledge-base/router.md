# Router — Chọn Technique

## Input cần có trước khi route
- `engine`: "omni_flash" | "agnes_ai" | (engine khác sau này)
- `scene_count`: số scene sau khi Scene Planning chia kịch bản
- `has_recurring_character`: true/false — nhân vật/sản phẩm xuất hiện lại nhiều scene
- `quota_mode`: "tiết_kiệm" | "bình_thường" — ưu tiên ít request hay không quan trọng
- `has_existing_video_to_fix`: true/false — đang sửa video đã tạo, không phải tạo mới

## Luật ưu tiên (đọc từ trên xuống, luật đầu tiên khớp thì dừng)

```
LUẬT 0 (luôn kiểm tra trước mọi nhánh):
  IF has_recurring_character == true:
      → chạy character-lock.md TRƯỚC, lấy character_sheet_image
      → rồi mới tiếp tục các luật bên dưới

LUẬT 1 — sửa video có sẵn:
  IF has_existing_video_to_fix == true AND engine.supports_edit == true:
      → technique = scene_extend_edit
  IF has_existing_video_to_fix == true AND engine.supports_edit == false:
      → technique = frame_to_frame_chain (generate lại đoạn lỗi như 1 scene mới,
        dùng frame liền kề làm anchor để khớp nối)

LUẬT 2 — chỉ 1 scene duy nhất:
  IF scene_count == 1:
      → technique = single_shot_direct
      (không cần storyboard hay chaining, tránh over-engineer)

LUẬT 3 — nhiều scene, engine hiểu bố cục đa cảnh (omni_flash):
  IF scene_count >= 2 AND engine.supports_storyboard_read == true:
      IF quota_mode == "tiết_kiệm":
          → technique = storyboard_sheet
      ELSE:
          → technique = frame_to_frame_chain
          (vẫn dùng được, cho phép edit/kiểm tra từng scene kỹ hơn,
           đổi lại tốn request hơn storyboard_sheet)

LUẬT 3B — nhiều scene, engine hỗ trợ keyframe array (agnes_ai):
  IF scene_count >= 2 AND engine.supports_keyframe_array == true:
      IF quota_mode == "tiết_kiệm":
          → technique = keyframe_array
          (1 request video cho nhiều keyframe, tốt hơn frame_to_frame_chain
           về quota mà không cần engine đọc bố cục phức tạp như storyboard_sheet)
      ELSE:
          → technique = frame_to_frame_chain
          (kiểm soát/duyệt từng scene kỹ hơn, chấp nhận tốn quota hơn)

LUẬT 4 — nhiều scene, engine KHÔNG hỗ trợ storyboard lẫn keyframe array:
  IF scene_count >= 2 AND engine.supports_storyboard_read == false
     AND engine.supports_keyframe_array == false:
      → technique = frame_to_frame_chain
      (fallback an toàn cuối cùng, hoạt động với mọi engine image-to-video cơ bản)
```

## Bảng quyết định rút gọn (tra nhanh)

| scene_count | engine hiểu storyboard? | engine hỗ trợ keyframe array? | quota_mode | → technique |
|---|---|---|---|---|
| 1 | - | - | - | single_shot_direct |
| ≥2 | Có | - | tiết_kiệm | storyboard_sheet |
| ≥2 | Có | - | bình_thường | frame_to_frame_chain |
| ≥2 | Không | Có | tiết_kiệm | keyframe_array |
| ≥2 | Không | Có | bình_thường | frame_to_frame_chain |
| ≥2 | Không | Không | - | frame_to_frame_chain |
| bất kỳ | (đang sửa video có sẵn) | - | - | scene_extend_edit (nếu engine hỗ trợ) |

**Engine hiện tại đã phân loại:** `omni_flash` = hiểu storyboard;
`agnes_ai` = hỗ trợ keyframe array (không hiểu storyboard sheet).

## Machine-readable summary
```yaml
rules:
  - id: R0_character_lock
    condition: "has_recurring_character == true"
    action: "run character-lock.md first, inject character_sheet_image into context"
    blocking: false  # không chặn, chỉ thêm bước trước
  - id: R1_edit_supported
    condition: "has_existing_video_to_fix == true AND engine.supports_edit == true"
    technique: scene_extend_edit
  - id: R1_edit_unsupported
    condition: "has_existing_video_to_fix == true AND engine.supports_edit == false"
    technique: frame_to_frame_chain
  - id: R2_single_scene
    condition: "scene_count == 1"
    technique: single_shot_direct
  - id: R3_multiscene_smart_engine_saving
    condition: "scene_count >= 2 AND engine.supports_storyboard_read == true AND quota_mode == 'tiết_kiệm'"
    technique: storyboard_sheet
  - id: R3_multiscene_smart_engine_normal
    condition: "scene_count >= 2 AND engine.supports_storyboard_read == true AND quota_mode == 'bình_thường'"
    technique: frame_to_frame_chain
  - id: R3B_multiscene_keyframe_saving
    condition: "scene_count >= 2 AND engine.supports_keyframe_array == true AND quota_mode == 'tiết_kiệm'"
    technique: keyframe_array
  - id: R3B_multiscene_keyframe_normal
    condition: "scene_count >= 2 AND engine.supports_keyframe_array == true AND quota_mode == 'bình_thường'"
    technique: frame_to_frame_chain
  - id: R4_multiscene_basic_engine
    condition: "scene_count >= 2 AND engine.supports_storyboard_read == false AND engine.supports_keyframe_array == false"
    technique: frame_to_frame_chain
```
