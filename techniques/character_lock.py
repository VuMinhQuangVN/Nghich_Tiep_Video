"""
techniques/character_lock.py
--------------------------------
Implement character-lock.md: chạy 1 LẦN cho mỗi nhân vật/sản phẩm (không
phải 1 lần mỗi scene) để tạo character_sheet_image dùng làm reference xuyên
suốt mọi scene, mọi technique.
"""
from __future__ import annotations

from core.prompt_composer import character_sheet_prompt
from core.vision_analyzer import VisionAnalyzer
from engines.base_engine import BaseEngine
from utils.logger import get_logger

log = get_logger(__name__)


class CharacterLock:
    def __init__(self, engine: BaseEngine):
        self._engine = engine
        self._vision = VisionAnalyzer(engine)

    async def build_character_sheet(self, reference_image_url: str, style: str) -> str:
        log.info("Chạy character-lock: phân tích ảnh mẫu + tạo character sheet...")
        subject_description = await self._vision.analyze(reference_image_url)
        prompt = character_sheet_prompt(subject_description, style)
        image = await self._engine.generate_image(prompt=prompt, ratio="1:1", size="2K")
        log.info(f"Character sheet đã tạo: {image.url_or_path}")
        return image.url_or_path
