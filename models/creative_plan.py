"""
models/creative_plan.py
------------------------
Data classes đơn giản — chỉ là carrier, không có logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CreativeInput:
    """Đầu vào từ người dùng."""
    product_reference_urls: list[str]
    goal: str
    platform: str
    duration_sec: float
    style_reference_urls: list[str] = field(default_factory=list)
    language: str = "vi"
    style: str = "Auto"
    aspect_ratio: str = "9:16"


@dataclass
class ShotPlan:
    """1 cảnh trong kịch bản."""
    index: int
    description: str          # Mô tả hành động (tiếng Việt)
    visual_prompt: str        # English prompt chi tiết cho AI gen ảnh/video
    voiceover: str            # Lời bình (tiếng Việt)
    duration: float           # Thời lượng thực tế (giây)
    common_visual_context: str = ""  # Context chung của toàn bộ video


@dataclass
class CreativePlan:
    """Kết quả sau khi AI phân tích và lên kịch bản."""
    title: str
    direction: str
    style_suggestion: str
    common_visual_context: str
    shots: list[ShotPlan]
    aspect_ratio: str = "9:16"
    total_duration: float = 0.0
