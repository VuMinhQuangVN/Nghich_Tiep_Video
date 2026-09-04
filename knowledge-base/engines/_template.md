# Engine: {TÊN_ENGINE}

## Trạng thái
{public preview / stable / free / trả phí / v.v.}

## Năng lực
- {liệt kê từng khả năng cụ thể}

## Giới hạn
- {liệt kê giới hạn}

## API cơ bản
```
{cú pháp gọi API/endpoint thực tế}
```

## Machine-readable summary
```yaml
engine_id: {snake_case_id}
status: {stable|preview|unverified}
free: {true|false}
capabilities:
  supports_storyboard_read: {true|false}
  supports_edit: {true|false}
  supports_image_to_video: {true|false}
  supports_audio_output: {true|false|null}
  supports_audio_input_for_sync: {true|false|null}
  max_clip_duration_sec: {number|null}
  min_clip_duration_sec: {number|null}
limitations:
  - "{...}"
recommended_techniques: [...]
```

---
Sau khi điền xong, thêm engine này vào bảng trong `router.md` nếu cần luật
riêng, và cập nhật `README.md` phần cấu trúc thư mục nếu muốn liệt kê tường minh.
