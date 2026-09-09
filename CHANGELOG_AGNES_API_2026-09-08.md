# Agnes API Contract Update — 2026-09-08

## Changed

- Primary image model is now `agnes-image-2.5-flash` by default.
- Primary video model is now `agnes-video-2.5-flash` by default.
- Added explicit `agnes-video-v2.0` stable fallback configuration.
- Video 2.5 Flash requests now follow the supplied documentation exactly:
  - top-level `mode`;
  - top-level `images`;
  - `mode=reference` for storyboard image → video;
  - `size=720P`;
  - `seconds` as integer string `4..12`;
  - `n=1`;
  - maximum 5 reference images.
- Video polling now remembers the concrete model used for each task and sends `model_name`.
- Shots outside the 2.5 Flash duration range are routed to V2.0 before an invalid request is sent.
- Temporary submit failures on 2.5 Flash can fall back to V2.0; invalid/auth failures are not treated as fallback-worthy.
- Product and style references remain separate in `SubjectLock`; both are supplied to storyboard image generation.
- Updated README and Agnes knowledge-base contracts.
- Added automated contract tests for image generation, Video 2.5 Flash, duration routing, and polling.

## Not included

- `.env`, `.git`, virtual environments, caches and generated output.
- The supplied external Agnes documentation files are source material, not copied into the project.
