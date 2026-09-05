from __future__ import annotations

import json
import re
from typing import Any

from engines.base_engine import BaseEngine
from core.platform_optimizer import build_platform_guidance, normalize_platform
from models.creative_plan import (
    AudienceProfile, CharacterProfile, CreativeConcept, CreativeInput,
    CreativePlan, ProductProfile, ScriptPlan, VisualStyle,
)


class CreativeDirector:
    """Phase 3: turn product understanding + user intent into creative direction."""

    DIRECTOR_PROMPT = """
Bạn là Creative Director của hệ thống AI tạo video quảng cáo sản phẩm.

Nhiệm vụ: xác định khách hàng mục tiêu; tạo concept và hook; chọn visual style;
quyết định có cần nhân vật; viết voice-over, text overlay và CTA.

QUY TẮC:
1. Sản phẩm là chủ thể chính và phải giữ nguyên nhận diện.
2. Không bịa claim, giá, thành phần, chứng nhận hoặc công dụng chưa được cung cấp.
3. Chỉ dùng character.required=true khi nhân vật thực sự cần cho concept.
4. Ý tưởng phải phù hợp goal, platform và duration.
5. Trả về DUY NHẤT JSON object hợp lệ, không markdown.

SCHEMA:
{
 "audience":{"age_range":"","gender":"","interests":[],"pain_points":[]},
 "concept":{"title":"","description":"","hook":""},
 "visual_style":{"style":"","lighting":"","color_palette":[],"camera_style":"","mood":""},
 "character":{"required":false,"description":"","reference_url":null},
 "script":{"voiceover":"","text_overlays":[],"cta":""}
}
""".strip()

    def __init__(self, engine: BaseEngine):
        self._engine = engine

    async def direct(self, creative_input: CreativeInput, product: ProductProfile) -> CreativePlan:
        self._validate_input(creative_input, product)
        raw = await self._engine.analyze_image(
            creative_input.product_reference_urls[0],
            self._build_prompt(creative_input, product),
        )
        return self._to_plan(creative_input, product, self._parse_response(raw))

    @staticmethod
    def _validate_input(i: CreativeInput, p: ProductProfile) -> None:
        if not i.product_reference_urls:
            raise ValueError("CreativeInput requires product reference URLs")
        if not i.goal.strip():
            raise ValueError("CreativeInput.goal must not be empty")
        if not i.platform.strip():
            raise ValueError("CreativeInput.platform must not be empty")
        if i.duration_sec <= 0:
            raise ValueError("CreativeInput.duration_sec must be greater than 0")
        if not p.name.strip() and not p.description.strip():
            raise ValueError("ProductProfile must contain product information")

    def _build_prompt(self, i: CreativeInput, p: ProductProfile) -> str:
        payload = {
            "input": {"goal": i.goal, "platform": normalize_platform(i.platform), "duration_sec": i.duration_sec, "language": i.language},
            "product": {"name": p.name, "category": p.category, "description": p.description,
                        "visual_identity": p.visual_identity, "selling_points": p.selling_points,
                        "consistency_requirements": p.consistency_requirements},
        }
        guidance = build_platform_guidance(i.platform)
        return f"{self.DIRECTOR_PROMPT}\n\n{guidance}\n\nDỮ LIỆU ĐẦU VÀO:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            s, e = text.find("{"), text.rfind("}")
            if s < 0 or e <= s:
                raise ValueError("Creative Director did not return valid JSON")
            try:
                data = json.loads(text[s:e + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("Creative Director did not return valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Creative Director response must be a JSON object")
        return data

    @staticmethod
    def _text(v: Any, default: str = "") -> str:
        return v.strip() if isinstance(v, str) else default

    @staticmethod
    def _list(v: Any) -> list[str]:
        return [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []

    @classmethod
    def _to_plan(cls, i: CreativeInput, p: ProductProfile, d: dict[str, Any]) -> CreativePlan:
        a, c, v, ch, s = (d.get(k) or {} for k in ("audience", "concept", "visual_style", "character", "script"))
        required = bool(ch.get("required", False))
        ch_desc = cls._text(ch.get("description"))
        if required and not ch_desc:
            raise ValueError("Creative Director marked character as required but provided no description")
        normalized_input = CreativeInput(
            product_reference_urls=list(i.product_reference_urls),
            goal=i.goal,
            platform=normalize_platform(i.platform),
            duration_sec=i.duration_sec,
            language=i.language,
        )
        return CreativePlan(
            input=normalized_input, product=p,
            audience=AudienceProfile(cls._text(a.get("age_range")), cls._text(a.get("gender")),
                                     cls._list(a.get("interests")), cls._list(a.get("pain_points"))),
            concept=CreativeConcept(cls._text(c.get("title")), cls._text(c.get("description")), cls._text(c.get("hook"))),
            visual_style=VisualStyle(cls._text(v.get("style")), cls._text(v.get("lighting")),
                                     cls._list(v.get("color_palette")), cls._text(v.get("camera_style")), cls._text(v.get("mood"))),
            character=CharacterProfile(required, ch_desc, ch.get("reference_url") if isinstance(ch.get("reference_url"), str) else None),
            script=ScriptPlan(cls._text(s.get("voiceover")), cls._list(s.get("text_overlays")), cls._text(s.get("cta"))),
            scenes=[],
        )
