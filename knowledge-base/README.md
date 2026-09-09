# Knowledge Base — AI Video Tool

Tài liệu kỹ thuật cho pipeline hiện tại.

## Runtime flow

```text
Product references
  → Creative Brain (5 candidates)
  → user selects one
  → storyboard image per shot
  → Agnes Video 2.5 Flash reference mode
  → trim theo editorial duration
  → concat
  → optional post-processing
```

## Nguyên tắc timeline

Creative Brain tự quyết số cảnh và nhịp dựng. Các ví dụ như 2–4s/cảnh,
`3+3+3+3+3` cho 15s hay `3+3+3+3+4+4` cho 20s chỉ là guidance, không phải
template hard-code. Tổng duration của candidate phải khớp duration người dùng.

## Model

- Text: `agnes-2.5-flash`
- Image: `agnes-image-2.5-flash`
- Video: `agnes-video-2.5-flash`
- Stable fallback: `agnes-video-v2.0`

Xem contract chi tiết trong các file `agnes-*.md` cùng thư mục.
