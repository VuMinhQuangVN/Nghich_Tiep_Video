# Agnes Video V2.0 — Stable Fallback

- Model: `agnes-video-v2.0`
- Status: STABLE / FALLBACK
- Submit: `POST /v1/videos`
- Poll: `GET /agnesapi?video_id=...`

## Contract

V2.0 uses the frame-based contract:

- `width` / `height`
- `num_frames` following `8n+1`, maximum `441`
- `frame_rate`
- standard ratios such as `16:9`, `9:16`, `1:1`, `4:3`, `3:4`

The Agnes client translates the pipeline's provider-neutral `reference` intent to the V2.0 image-to-video form when fallback is required.
