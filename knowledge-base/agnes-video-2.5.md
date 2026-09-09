# Agnes Video 2.5 — Trial

- Model: `agnes-video-2.5`
- Status: TRIAL / EXPERIMENTAL
- Default: **disabled**
- Config: `AGNES_VIDEO_25_ENABLED=false`
- Fallback: `agnes-video-v2.0`

## Availability

The application does not assume that every API key has entitlement. Local availability is represented by the feature flag; real entitlement/quota failures during submit or polling are treated as fallback-worthy runtime failures.

## Request / polling

The adapter reuses the provider-neutral `/videos` submit and `/agnesapi` polling contract exposed by `AgnesClient`. Provider-specific differences remain inside the adapter.

## Safety rules

- Never select Trial automatically in Simple Mode.
- Do not retry invalid requests forever.
- Do not disable TLS verification.
- On unavailable/temporary failure, fall back to V2.0.
