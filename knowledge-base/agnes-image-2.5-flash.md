# Agnes Image 2.5 Flash — Image Engine

- Model: `agnes-image-2.5-flash`
- Endpoint: `POST /v1/images/generations`
- Current status: primary image model
- Current price in the supplied documentation: `$0` (limited-time/current pricing can change)
- Modes: text-to-image, image-to-image, multi-image composition
- Reference images: `extra_body.image` as an array; public URL or Data URI Base64
- `response_format`: inside `extra_body`, not top-level
- Ratio: `1:1`, `3:4`, `4:3`, `16:9`, `9:16`, `2:3`, `3:2`, `21:9`
- Recommended resolution tiers: `1K`, `2K`, `3K`, `4K`

The application keeps product references and style references separate at the SubjectLock layer, then sends both to the image generator so the generated storyboard can inherit product identity and requested visual style.
