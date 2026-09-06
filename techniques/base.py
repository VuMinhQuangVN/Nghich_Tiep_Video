"""
techniques/base.py
---------------------
Strategy Pattern: mỗi technique (single_shot_direct, frame_to_frame_chain,
keyframe_array, ...) implement cùng 1 interface `run()`. router.py chỉ chọn
TÊN technique; pipeline_runner.py map tên -> instance rồi gọi `.run()` mà
không cần biết chi tiết bên trong -> Open/Closed Principle (thêm technique
mới không cần sửa pipeline_runner).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from models.creative_plan import CreativePlan, CreativeScene
from models.image_request import image_ratio_for_platform, normalize_image_ratio, normalize_image_resolution
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock


@dataclass
class TechniqueContext:
    scenes: list[CreativeScene]
    style: str
    subject_name: str
    character_sheet_url: str | None
    output_dir: Path
    max_concurrent_image_requests: int
    max_concurrent_video_submit: int
    poll_interval_sec: float
    product_reference_url: str | None = None
    product_reference_urls: list[str] = field(default_factory=list)
    image_ratio: str = "9:16"
    image_resolution: str = "2K"
    # Phase 6/7 wiring: shot-level plans and deterministic final prompts.
    shot_plans: dict[int, list[CreativeShot]] = field(default_factory=dict)
    shot_prompts: dict[int, list[str]] = field(default_factory=dict)
    creative_plan: CreativePlan | None = None
    subject_lock: SubjectLock | None = None


@dataclass
class TechniqueResult:
    final_video_path: Path
    segment_video_paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BaseTechnique(ABC):
    @staticmethod
    def image_generation_settings(ctx: TechniqueContext) -> tuple[str, str]:
        return (normalize_image_ratio(ctx.image_ratio), normalize_image_resolution(ctx.image_resolution))

    @staticmethod
    def product_reference_images(ctx: TechniqueContext) -> list[str]:
        """Return every product reference, plus an optional character sheet.

        Keep order deterministic and remove duplicates so engines receive one
        canonical reference list. Legacy callers that only set
        ``product_reference_url`` continue to work.
        """
        refs = list(ctx.product_reference_urls)
        if not refs and ctx.product_reference_url:
            refs.append(ctx.product_reference_url)
        if ctx.character_sheet_url:
            refs.append(ctx.character_sheet_url)

        result: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            if not isinstance(ref, str) or not ref.strip():
                continue
            ref = ref.strip()
            if ref not in seen:
                seen.add(ref)
                result.append(ref)
        return result

    @staticmethod
    def prompts_for_scene(ctx: TechniqueContext, scene: CreativeScene) -> list[str]:
        """Return Phase 7 final prompts for a scene, preserving legacy fallback."""
        prompts = [p.strip() for p in ctx.shot_prompts.get(scene.index, []) if isinstance(p, str) and p.strip()]
        if prompts:
            return prompts
        return [scene.description.strip()]

    @classmethod
    def combined_prompt_for_scene(cls, ctx: TechniqueContext, scene: CreativeScene) -> str:
        prompts = cls.prompts_for_scene(ctx, scene)
        if len(prompts) == 1:
            return prompts[0]
        return "\n\nSHOT SEQUENCE:\n" + "\n--- NEXT SHOT ---\n".join(prompts)

    @abstractmethod
    async def run(self, ctx: TechniqueContext) -> TechniqueResult:
        raise NotImplementedError
