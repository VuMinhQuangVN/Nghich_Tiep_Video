# Agnes Integration

## Architecture

```text
Creative Pipeline
      ↓
GenerationFacade
      ├── Brain/Image → AgnesClient
      └── Video → VideoEngine
                    ├── V2.0 Stable
                    ├── 2.5 Flash Experimental
                    └── 2.5 Trial
```

Pipeline code must not branch on Agnes model IDs. Model selection belongs to the router/factory layer.

## Routing

- Simple/Auto → V2.0 Stable.
- Experimental → 2.5 Flash with V2.0 fallback.
- Explicit Trial → 2.5 with V2.0 fallback.

## Reliability

Retry only temporary conditions: timeout, network errors, 429 and 5xx. Do not retry 400/401/403/invalid-model requests indefinitely. Key rotation is independent from model selection.

## Polling

Polling is lightweight and must not use generation cooldown. `VideoJob` is the provider-neutral state contract.

## Security

HTTPS certificate verification remains enabled. API keys never appear in UI or logs.


## Editorial duration rule (2026-09-08)
The creative `shot.duration` is the final editorial duration. Provider generation duration is separate. For short ads, generate a provider-supported clip (e.g. 4s minimum on Video 2.5 Flash), trim it with FFmpeg to the shot duration, then concatenate. Never sum provider generation durations as the final movie duration.
