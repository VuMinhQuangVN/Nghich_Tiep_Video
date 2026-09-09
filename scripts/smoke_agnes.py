"""Optional live Agnes smoke test.

Usage:
    AGNES_SMOKE_LIVE=true python scripts/smoke_agnes.py

Without AGNES_SMOKE_LIVE the script only validates local SSL/config wiring.
"""
from __future__ import annotations

import asyncio
import os

from config import settings
from engines.agnes_client import AgnesClient
from utils.key_rotation import KeyRotator


async def main() -> None:
    settings.validate()
    keys = KeyRotator(settings.agnes_api_keys, cooldown_base_sec=0, cooldown_max_sec=0)
    async with AgnesClient(keys) as client:
        print("SSL/config OK:", settings.agnes_base_url)
        if os.getenv("AGNES_SMOKE_LIVE", "false").lower() not in {"1", "true", "yes", "on"}:
            return
        result = await client._post(
            settings.agnes_endpoints.chat_completions,
            {"model": settings.agnes_models.text,
             "messages": [{"role": "user", "content": "Reply only: OK"}]},
            throttled=False,
        )
        print("Agnes chat OK:", result["choices"][0]["message"]["content"])


if __name__ == "__main__":
    asyncio.run(main())
