"""Provider-neutral asynchronous video job contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoJob:
    job_id: str
    model: str
    status: VideoJobStatus = VideoJobStatus.QUEUED
    result_url: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status == VideoJobStatus.COMPLETED

    @property
    def failed(self) -> bool:
        return self.status == VideoJobStatus.FAILED
