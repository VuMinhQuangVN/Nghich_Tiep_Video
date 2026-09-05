from __future__ import annotations

import json
import re
from typing import Any, Iterable

from engines.base_engine import BaseEngine
from models.creative_plan import ProductProfile


class ProductAnalyzer:
    """Analyze product reference images and convert them to ProductProfile."""

    ANALYSIS_PROMPT = """
Bạn là chuyên gia phân tích sản phẩm cho hệ thống AI tạo video quảng cáo.
Quan sát sản phẩm trong ảnh và trả về DUY NHẤT một JSON object hợp lệ.
Không markdown, không ```json, không giải thích bên ngoài JSON.

Schema:
{
  "name": "tên sản phẩm nếu nhận biết được, nếu không dùng mô tả ngắn",
  "category": "loại sản phẩm",
  "description": "mô tả ngắn, khách quan về sản phẩm và hình dáng",
  "visual_identity": "đặc điểm nhận diện hình ảnh cần giữ nhất quán",
  "selling_points": ["điểm nổi bật có thể dùng trong quảng cáo"],
  "consistency_requirements": ["chi tiết tuyệt đối không được tự ý thay đổi"]
}

Chỉ suy luận những gì có thể quan sát hoặc hợp lý từ ảnh. Không bịa thông số,
giá, thành phần, công dụng hoặc chứng nhận không nhìn thấy/không được cung cấp.
""".strip()

    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def analyze(self, reference_urls: list[str]) -> ProductProfile:
        urls = [url.strip() for url in reference_urls if url and url.strip()]
        if not urls:
            raise ValueError("Cần ít nhất một product reference URL")

        analyses: list[dict[str, Any]] = []
        for url in urls:
            raw = await self._engine.analyze_image(url, self.ANALYSIS_PROMPT)
            analyses.append(self._parse_response(raw))

        return self._merge(analyses)

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return {"description": text}
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {"description": text}

        return data if isinstance(data, dict) else {"description": text}

    @staticmethod
    def _unique(values: Iterable[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                result.append(value)

        return result

    @classmethod
    def _merge(cls, analyses: list[dict[str, Any]]) -> ProductProfile:
        def first_text(key: str, fallback: str = "") -> str:
            for item in analyses:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return fallback

        descriptions = cls._unique(
            item.get("description") for item in analyses
        )

        selling_points = cls._unique(
            point
            for item in analyses
            for point in (item.get("selling_points") or [])
        )

        consistency = cls._unique(
            point
            for item in analyses
            for point in (item.get("consistency_requirements") or [])
        )

        return ProductProfile(
            name=first_text("name", "Unknown product"),
            category=first_text("category", "Unknown"),
            description=" ".join(descriptions),
            visual_identity=first_text("visual_identity"),
            selling_points=selling_points,
            consistency_requirements=consistency,
        )
