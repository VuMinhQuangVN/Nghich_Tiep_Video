"""
orchestrator/pipeline_runner.py
-----------------------------------
Nhạc trưởng chính, map thẳng với luồng UI 4 bước trong software-design.md:
  Bước 1: Input (do CLI/main.py thu thập, truyền vào đây)
  Bước 2: Scene Planning (tuần tự, 1 lệnh gọi LLM) + Router chọn technique
  Bước 3: (character-lock nếu cần) rồi build ảnh/keyframe
  Bước 4: Render video theo technique đã chọn, rồi ghép nối kết quả

Chỉ phụ thuộc vào BaseEngine (interface), không phụ thuộc AgnesClient trực
tiếp -> Dependency Inversion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.router import QuotaMode, RouterInput, Technique, choose_technique
from core.scene_planner import ScenePlanner
from core.shot_planner import ShotPlanner
from core.prompt_composer import PromptComposer
from models.creative_plan import CreativePlan
from models.image_request import image_ratio_for_platform
from models.shot_plan import CreativeShot
from models.subject_lock import SubjectLock
from engines.base_engine import BaseEngine
from techniques.base import TechniqueContext, TechniqueResult
from techniques.character_lock import CharacterLock
from techniques.frame_to_frame_chain import FrameToFrameChain
from techniques.keyframe_array import KeyframeArray
from techniques.single_shot_direct import SingleShotDirect
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class PipelineInput:
    script_text: str
    style_hint: str
    subject_name: str
    reference_image_url: str | None      # ảnh mẫu chất lượng thấp, chỉ để phân tích
    keep_character_consistent: bool       # toggle Bước 1
    quota_mode: QuotaMode                 # radio Bước 2
    max_concurrent_image_requests: int
    max_concurrent_video_submit: int
    poll_interval_sec: float
    output_dir: Path
    # Phase 10 creative hand-off. Optional to preserve legacy callers.
    product_reference_url: str | None = None
    # Phase 13: all product references are forwarded to image generation.
    product_reference_urls: list[str] = field(default_factory=list)
    image_ratio: str | None = None
    image_resolution: str = "2K"
    creative_plan: CreativePlan | None = None
    subject_lock: SubjectLock | None = None


# Các technique KHÔNG được Agnes hỗ trợ (storyboard_sheet, scene_extend_edit)
# sẽ chưa có implementation ở bản này -> báo lỗi rõ ràng thay vì chạy sai.
_UNSUPPORTED_ON_AGNES = {Technique.STORYBOARD_SHEET, Technique.SCENE_EXTEND_EDIT}


class PipelineRunner:
    def __init__(self, engine: BaseEngine):
        self._engine = engine
        self._scene_planner = ScenePlanner(engine)
        self._shot_planner = ShotPlanner(engine)
        self._prompt_composer = PromptComposer()
        self._character_lock = CharacterLock(engine)

    async def run(self, inp: PipelineInput) -> TechniqueResult:
        inp.output_dir.mkdir(parents=True, exist_ok=True)

        # ---- Bước 2: Scene Planning ----
        # Phase 10 consumes the approved CreativePlan/SubjectLock. Legacy
        # callers continue to use the old script_text/style_hint contract.
        shot_plans: dict[int, list[CreativeShot]] = {}
        shot_prompts: dict[int, list[str]] = {}

        if inp.creative_plan is not None:
            if inp.subject_lock is None:
                raise ValueError("CreativePlan input requires SubjectLock")
            scenes = await self._scene_planner.plan_creative(inp.creative_plan, inp.subject_lock)

            # ---- Phase 6: Scene -> Shot planning ----
            shot_plans = await self._shot_planner.plan(
                scenes, inp.creative_plan, inp.subject_lock
            )

            # ---- Phase 7: Shot -> deterministic final engine prompts ----
            # PromptComposer never calls the network. It assembles the approved
            # creative context + SubjectLock + scene + shot into the exact
            # prompt that the selected generation technique will send to Agnes.
            for scene in scenes:
                prompts = [
                    self._prompt_composer.compose_shot_prompt(
                        inp.creative_plan,
                        inp.subject_lock,
                        scene,
                        shot,
                    )
                    for shot in shot_plans.get(scene.index, [])
                ]
                if not prompts:
                    raise RuntimeError(
                        f"Scene {scene.index} không có shot prompt sau Phase 6/7"
                    )
                shot_prompts[scene.index] = prompts

            log.info(
                "Phase 6/7 hoàn tất: %s scene -> %s shot -> %s final prompt",
                len(scenes),
                sum(len(items) for items in shot_plans.values()),
                sum(len(items) for items in shot_prompts.values()),
            )
        else:
            scenes = await self._scene_planner.plan(inp.script_text, inp.style_hint)
        if not scenes:
            raise RuntimeError("Scene planner không trả về scene nào — kiểm tra lại kịch bản input")

        # ---- LUẬT 0: character-lock TRƯỚC router (nếu cần) ----
        character_sheet_url: str | None = None
        if inp.keep_character_consistent:
            if not inp.reference_image_url:
                raise ValueError(
                    "Đã bật 'giữ nhân vật nhất quán' nhưng không có ảnh mẫu — "
                    "cần validate ở Bước 1 UI trước khi tới đây."
                )
            character_sheet_url = await self._character_lock.build_character_sheet(
                inp.reference_image_url, inp.style_hint
            )

        # ---- Router chọn technique ----
        router_input = RouterInput(
            engine_capabilities=self._engine.capabilities,
            scene_count=len(scenes),
            has_recurring_character=inp.keep_character_consistent,
            quota_mode=inp.quota_mode,
            has_existing_video_to_fix=False,
        )
        technique_name = choose_technique(router_input)
        log.info(f"Router chọn technique: [bold]{technique_name.value}[/bold]")

        if technique_name in _UNSUPPORTED_ON_AGNES:
            raise NotImplementedError(
                f"Technique '{technique_name.value}' chưa được engine hiện tại hỗ trợ "
                f"(Agnes AI không có supports_storyboard_read/supports_edit). "
                f"Cần engine khác (VD: Omni Flash) hoặc bổ sung implementation."
            )

        technique = self._build_technique(technique_name)

        # ---- Bước 3 + 4: chạy technique đã chọn ----
        image_ratio = inp.image_ratio
        if image_ratio is None and inp.creative_plan is not None:
            image_ratio = image_ratio_for_platform(inp.creative_plan.input.platform)
        image_ratio = image_ratio or "9:16"

        ctx = TechniqueContext(
            scenes=scenes,
            style=inp.style_hint,
            subject_name=inp.subject_name,
            character_sheet_url=character_sheet_url,
            output_dir=inp.output_dir,
            max_concurrent_image_requests=inp.max_concurrent_image_requests,
            max_concurrent_video_submit=inp.max_concurrent_video_submit,
            poll_interval_sec=inp.poll_interval_sec,
            product_reference_url=inp.product_reference_url,
            product_reference_urls=list(inp.product_reference_urls),
            image_ratio=image_ratio,
            image_resolution=inp.image_resolution,
            shot_plans=shot_plans,
            shot_prompts=shot_prompts,
            creative_plan=inp.creative_plan,
            subject_lock=inp.subject_lock,
        )
        result = await technique.run(ctx)

        for w in result.warnings:
            log.warning(w)
        log.info(f"[bold green]Hoàn tất![/bold green] Video cuối: {result.final_video_path}")
        return result

    def _build_technique(self, name: Technique):
        mapping = {
            Technique.SINGLE_SHOT_DIRECT: lambda: SingleShotDirect(self._engine),
            Technique.KEYFRAME_ARRAY: lambda: KeyframeArray(self._engine),
            Technique.FRAME_TO_FRAME_CHAIN: lambda: FrameToFrameChain(self._engine),
        }
        factory = mapping.get(name)
        if factory is None:
            raise NotImplementedError(f"Chưa có implementation cho technique '{name.value}'")
        return factory()
