"""
core/product_analyzer.py
-------------------------
Stub — logic phân tích sản phẩm đã được gộp vào CreativeDirector.
Giữ file này để job_manager không lỗi import.
"""
from __future__ import annotations


class ProductAnalyzer:
    """Không còn dùng riêng — CreativeDirector đã gộp phân tích vào 1 bước."""

    def __init__(self, engine):
        self._engine = engine

    async def analyze(self, image_urls: list[str]) -> dict:
        # Trả dict rỗng — CreativeDirector tự phân tích ảnh khi direct()
        return {}
