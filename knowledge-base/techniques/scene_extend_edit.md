# Technique: Scene Extend / Edit-in-place

## Bản chất
Sửa 1 video ĐÃ TẠO bằng prompt ngôn ngữ tự nhiên, thay vì generate lại từ
đầu. Engine giữ nguyên phần không được yêu cầu sửa, chỉ áp dụng thay đổi vào
đúng phần được chỉ định.

## Chỉ dùng khi
- `engine.supports_edit == true` (hiện chỉ xác nhận có ở Omni Flash — xem
  `engines/omni_flash.md`)
- Đã có 1 video/scene tạo ra trước đó nhưng có lỗi nhỏ cần sửa (VD: hành động
  sai thời điểm, chi tiết bối cảnh sai, muốn đổi góc camera 1 đoạn) — KHÔNG
  dùng cho lỗi lớn (sai hoàn toàn chủ thể/bối cảnh, lúc đó nên generate lại).

## Quy trình

1. Xác định rõ phần cần sửa (mô tả càng cụ thể càng tốt, tránh mơ hồ).
2. Sinh prompt edit:

```
Edit this video: {mô tả thay đổi cụ thể, VD: "change the door to open 2
seconds later" / "make the camera pan slower in the first half"}.
Keep everything else unchanged — same subject, same lighting, same style.
```

3. Gọi engine: video edit, kèm video gốc + prompt trên (KHÔNG kèm ảnh mới,
   vì mục đích là sửa dựa trên context video đã có).
4. Nếu edit không đạt (do giới hạn model ở bản preview), fallback:
   generate lại đoạn đó bằng `frame_to_frame_chain`, dùng frame liền kề của
   đoạn trước/sau làm anchor để khớp nối.

## Lưu ý giới hạn (theo tài liệu Omni Flash, có thể thay đổi vì đang preview)
- Chưa hỗ trợ nhận audio làm input để đồng bộ chuyển động theo voiceover có sẵn.
- Một số trường hợp edit đổi cảnh vẫn có thể ảnh hưởng tính nhất quán nhân vật
  — nên luôn preview kết quả trước khi ghép vào video cuối.

## Ưu / Nhược
| | |
|---|---|
| Ưu | Tiết kiệm quota đáng kể so với generate lại toàn bộ; giữ nguyên phần đã đúng |
| Nhược | Chỉ có ở engine hỗ trợ (không phải mọi engine có); còn là tính năng preview, độ ổn định có thể thay đổi |

## Machine-readable summary
```yaml
technique_id: scene_extend_edit
requires_engine_capability: ["supports_edit"]
quota_cost: "low (1 edit call vs full regeneration)"
consistency_risk: "low (edits preserve unspecified parts)"
fallback_if_engine_unsupported: frame_to_frame_chain
status_note: "engine feature may be in preview; verify stability before relying on it in production"
```
