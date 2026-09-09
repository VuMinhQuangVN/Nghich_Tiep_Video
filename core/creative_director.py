"""
core/creative_director.py
--------------------------
1 lần gọi AI → ra thẳng shot list hoàn chỉnh.
Học từ Flow app: gộp phân tích sản phẩm + lên kịch bản vào 1 prompt duy nhất.
Không phase, không oằn tà loàn.
"""
from __future__ import annotations

import json
from utils.logger import get_logger
from models.creative_plan import CreativeInput, CreativePlan, ShotPlan

log = get_logger(__name__)


class CreativeDirector:
    """Nhận engine AI + input sáng tạo → tạo kịch bản có nhịp dựng rõ ràng."""

    def __init__(self, engine):
        if engine is None:
            raise ValueError("CreativeDirector cần một AI engine")
        self._engine = engine

    async def direct(self, creative_input: CreativeInput) -> CreativePlan:
        """Backward-compatible: brainstorm 5 candidates and return the first one."""
        candidates = await self.brainstorm(creative_input)
        return candidates[0]

    async def brainstorm(self, creative_input: CreativeInput) -> list[CreativePlan]:
        """One AI call -> 5 genuinely different creative directions.

        The AI decides the shot count and pacing. Examples such as 15s/20s/30s are
        guidance only; no hard-coded shot pattern is imposed here.
        """
        log.info("CreativeDirector: đang brainstorm 5 phương án kịch bản...")
        total_sec = float(creative_input.duration_sec)
        style = creative_input.style if creative_input.style != "Auto" else ""
        style_instruction = f"Style phim: {style}." if style else "Tự đề xuất style phù hợp nhất với sản phẩm."

        prompt = f"""Bạn là Creative Director + đạo diễn quảng cáo bán sản phẩm cho TikTok/Reels/Shorts.

Phân tích ảnh sản phẩm và tạo ĐÚNG 5 PHƯƠNG ÁN KỊCH BẢN KHÁC NHAU trong MỘT lần suy luận.
Mục tiêu là để người dùng xem 5 phương án, chọn phương án hay nhất rồi hệ thống mới sản xuất video.

MỤC TIÊU: {creative_input.goal}
NỀN TẢNG: {creative_input.platform}
TỔNG THỜI LƯỢNG BIÊN TẬP CUỐI: chính xác {total_sec:g} giây
TỈ LỆ: {creative_input.aspect_ratio}
NGÔN NGỮ VOICEOVER: {creative_input.language}
{style_instruction}

QUAN TRỌNG VỀ TIMELINE:
- Hãy TỰ SUY NGHĨ số cảnh và thời lượng từng cảnh sao cho nhịp quảng cáo tốt nhất.
- Không có công thức cứng cho 15s, 20s hay 30s. Các ví dụ 2-4s/cảnh, 3+3+3+3+3 hoặc 3+3+3+3+4+4 chỉ là THAM KHẢO về nhịp, không phải luật.
- Với short product ads, thường cảnh ngắn giúp video có nhịp nhanh, nhưng có thể dùng cảnh dài hơn khi một demo/visual cần thời gian.
- Tổng duration các cảnh PHẢI bằng chính xác {total_sec:g} giây.
- Duration là thời lượng BIÊN TẬP CUỐI; AI video provider có thể generate clip dài hơn rồi hệ thống trim.
- Nếu 30s cần 7, 8, 9 hoặc 10 cảnh thì cứ chọn số cảnh hợp lý; đừng ép theo mẫu.

MỖI PHƯƠNG ÁN PHẢI KHÁC VỀ Ý TƯỞNG, KHÔNG CHỈ ĐỔI TỪ NGỮ. Ví dụ có thể cân nhắc:
- pain-point → solution
- visual/product-first
- demo/feature-first
- before/after hoặc transformation
- UGC/testimonial/social-proof
Nhưng hãy tự chọn cấu trúc tốt nhất theo sản phẩm, không bắt buộc dùng các mẫu trên.

MỖI PHƯƠNG ÁN cần có:
- title
- direction: ý tưởng kể chuyện ngắn gọn
- styleSuggestion
- commonVisualContext bằng tiếng Anh
- shots: từng cảnh có id, description tiếng Việt, visualPrompt tiếng Anh, voiceover tiếng Việt, duration
- ratingReason: vì sao phương án này có tiềm năng bán hàng
- hookStrength: đánh giá Hook
- conversionAngle: góc chuyển đổi/chốt đơn

Không bịa logo/chức năng/claim y tế hoặc thông số không có trong ảnh/input.
Voiceover phải ngắn, tự nhiên, nói vừa thời lượng cảnh.

Chỉ trả JSON hợp lệ, không markdown:
{{
  "candidates": [
    {{
      "title": "...",
      "direction": "...",
      "styleSuggestion": "...",
      "commonVisualContext": "...",
      "ratingReason": "...",
      "hookStrength": "strong",
      "conversionAngle": "...",
      "shots": [
        {{"id": 1, "description": "...", "visualPrompt": "...", "voiceover": "...", "duration": 3}}
      ]
    }}
  ]
}}"""
        raw = await self._engine.analyze_with_images(
            images=creative_input.product_reference_urls,
            prompt=prompt,
        )
        data = _parse_json(raw)
        raw_candidates = data.get("candidates", [])
        if not isinstance(raw_candidates, list) or len(raw_candidates) < 5:
            raise ValueError(f"AI phải trả về 5 kịch bản, nhưng nhận được {len(raw_candidates) if isinstance(raw_candidates, list) else 0}")

        plans: list[CreativePlan] = []
        for candidate in raw_candidates[:5]:
            plans.append(_candidate_to_plan(candidate, creative_input, total_sec))
        log.info("CreativeDirector: đã tạo 5 phương án kịch bản; chưa chạy pipeline")
        return plans


def _candidate_to_plan(data: dict, creative_input: CreativeInput, target: float) -> CreativePlan:
    raw_shots = data.get("shots", []) if isinstance(data, dict) else []
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("Một candidate không có shot list hợp lệ")
    shots = []
    for idx, item in enumerate(raw_shots, start=1):
        if not isinstance(item, dict):
            continue
        shots.append(ShotPlan(
            index=int(item.get("id", idx)),
            description=str(item.get("description", "")).strip(),
            visual_prompt=str(item.get("visualPrompt", "")).strip(),
            voiceover=str(item.get("voiceover", "")).strip(),
            duration=max(0.1, float(item.get("duration", 3))),
            common_visual_context=str(data.get("commonVisualContext", "")),
        ))
    if not shots:
        raise ValueError("Candidate không có shot hợp lệ")
    shots = _normalize_editorial_timeline(shots, target)
    return CreativePlan(
        title=str(data.get("title", "Video quảng cáo")),
        direction=str(data.get("direction", "")),
        style_suggestion=str(data.get("styleSuggestion", "cinematic")),
        common_visual_context=str(data.get("commonVisualContext", "")),
        shots=shots,
        aspect_ratio=creative_input.aspect_ratio,
        total_duration=sum(s.duration for s in shots),
    )


def _normalize_editorial_timeline(shots: list[ShotPlan], target: float) -> list[ShotPlan]:
    """Keep the AI's structure/pacing, only make the final timeline exact."""
    total = sum(s.duration for s in shots)
    if total <= 0:
        raise ValueError("Timeline AI trả về không hợp lệ")
    factor = target / total
    for shot in shots:
        shot.duration = round(shot.duration * factor, 3)
    drift = round(target - sum(s.duration for s in shots), 3)
    shots[-1].duration = round(shots[-1].duration + drift, 3)
    for idx, shot in enumerate(shots, 1):
        shot.index = idx
    return shots


def _parse_json(raw: str) -> dict:
    """Parse JSON từ response AI, xử lý cả trường hợp AI bọc trong markdown."""
    text = raw.strip()
    # Bỏ markdown code block nếu có
    for marker in ("```json", "```"):
        if text.startswith(marker):
            text = text[len(marker):]
    text = text.removesuffix("```").strip()
    # Tìm JSON object
    start = text.find("{")
    if start != -1:
        text = text[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI trả về JSON không hợp lệ: {raw[:500]}") from e
