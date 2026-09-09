# Agnes Video 2.5 Flash — Primary Video Engine

- Model: `agnes-video-2.5-flash`
- Endpoint: `POST /v1/videos`
- Poll: `GET /agnesapi?video_id=<VIDEO_ID>&model_name=agnes-video-2.5-flash`
- Current status: PRIMARY
- Fallback: `agnes-video-v2.0`
- Current price in the supplied documentation: `$0/second` (limited-time/current pricing can change)

## Request contract

For storyboard image → video, use **reference mode**:

```json
{
  "model": "agnes-video-2.5-flash",
  "prompt": "...",
  "seconds": "5",
  "mode": "reference",
  "size": "720P",
  "aspect_ratio": "9:16",
  "images": ["https://public-image-url.example/storyboard.png"],
  "n": 1
}
```

Important:

- `mode`, `images`, `size`, `seconds`, `aspect_ratio`, `n` are top-level fields.
- Do **not** send Video 2.5 Flash media through `extra_body.image` / `extra_body.mode`.
- `mode=reference` requires at least one non-empty `images` or `audios` entry.
- Maximum 5 reference images.
- Flash only accepts `size="720P"`.
- `seconds` is a string and must be an integer from `4` through `12`.
- `n` is `1`.
- Media URLs must remain publicly accessible until generation completes.

## Polling

For reference/keyframe generations, include both `video_id` and `model_name`. The application records the concrete model used for every submitted video task so polling uses the same model automatically.

## Short clips

A requested shot below 4 seconds cannot be sent to Video 2.5 Flash. The facade automatically selects the configured V2.0 stable fallback for such a shot when available.
