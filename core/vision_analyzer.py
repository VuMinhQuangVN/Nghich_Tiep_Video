"""
core/vision_analyzer.py
--------------------------
Bước "phân tích ảnh mẫu chất lượng thấp" trong character-lock.md.
Chỉ phụ thuộc vào BaseEngine (interface), không phụ thuộc AgnesClient trực
tiếp -> dễ test bằng fake engine, dễ đổi engine sau này.
"""
from __future__ import annotations

from engines.base_engine import BaseEngine
from utils.logger import get_logger

log = get_logger(__name__)

ANALYSIS_QUESTION = (
    "Mô tả chi tiết chủ thể trong ảnh này để dùng làm reference cho character "
    "sheet: hình dạng khuôn mặt, đặc điểm nhận diện, trang phục, tỉ lệ cơ thể, "
    "tông màu chủ đạo, và phong cách hình ảnh (ảnh thật / 3D render / anime / "
    "khác). Trả lời ngắn gọn, súc tích, dạng mô tả liệt kê."
)


class VisionAnalyzer:
    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def analyze(self, reference_image_url: str) -> str:
        log.info(f"Phân tích ảnh mẫu: {reference_image_url}")
        description = await self._engine.analyze_image(reference_image_url, ANALYSIS_QUESTION)
        return description.strip()
