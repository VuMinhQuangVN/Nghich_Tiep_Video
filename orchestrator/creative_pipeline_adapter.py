"""Phase 10: adapt an approved CreativePlan to the existing generation pipeline.

The creative layer owns intent and creative decisions. The generation layer
continues to own technique execution, polling and FFmpeg. This adapter is the
single translation boundary between the two layers.
"""
from __future__ import annotations

from pathlib import Path

from core.router import QuotaMode
from models.creative_plan import CreativePlan
from models.subject_lock import SubjectLock
from utils.video_post_processor import PostProcessOptions, TextOverlay
from orchestrator.pipeline_runner import PipelineInput


class CreativePipelineAdapter:
    """Translate CreativePlan + SubjectLock into PipelineInput."""

    @staticmethod
    def to_post_process_options(
        creative_plan: CreativePlan,
        *,
        voiceover_path: Path | None = None,
        background_music_path: Path | None = None,
        subtitles_path: Path | None = None,
    ) -> PostProcessOptions:
        """Translate CreativePlan script/scene copy into Phase 11 options.

        Audio/subtitle files are explicit external inputs. Text overlays and CTA
        come from the approved CreativePlan so the creative decision is actually
        reflected in the final video.
        """
        if not isinstance(creative_plan, CreativePlan):
            raise TypeError("creative_plan phải là CreativePlan")

        overlays: list[TextOverlay] = []
        cursor = 0.0
        scene_ctas: list[TextOverlay] = []

        for scene in creative_plan.scenes:
            duration = max(float(scene.duration_sec), 0.0)
            if scene.text_overlay.strip():
                overlays.append(
                    TextOverlay(
                        text=scene.text_overlay.strip(),
                        start_sec=cursor,
                        end_sec=cursor + duration,
                        position="bottom",
                    )
                )
            if scene.cta.strip():
                scene_ctas.append(
                    TextOverlay(
                        text=scene.cta.strip(),
                        start_sec=cursor,
                        end_sec=cursor + duration,
                        position="bottom",
                    )
                )
            cursor += duration

        # If scene-level copy is absent, retain script-level overlays.
        if not overlays:
            total_duration = max(float(creative_plan.input.duration_sec), 0.0)
            overlays.extend(
                TextOverlay(
                    text=text.strip(),
                    start_sec=0.0,
                    end_sec=total_duration or None,
                    position="bottom",
                )
                for text in creative_plan.script.text_overlays
                if isinstance(text, str) and text.strip()
            )

        cta = scene_ctas[0] if scene_ctas else None
        if cta is None and creative_plan.script.cta.strip():
            cta = TextOverlay(
                text=creative_plan.script.cta.strip(),
                start_sec=0.0,
                end_sec=None,
                position="bottom",
            )

        return PostProcessOptions(
            voiceover_path=voiceover_path,
            background_music_path=background_music_path,
            subtitles_path=subtitles_path,
            text_overlays=overlays,
            cta=cta.text if cta else None,
            cta_start_sec=cta.start_sec if cta else None,
        )

    @staticmethod
    def to_pipeline_input(
        creative_plan: CreativePlan,
        subject_lock: SubjectLock,
        *,
        output_dir: Path,
        quota_mode: QuotaMode = QuotaMode.SAVE,
        max_concurrent_image_requests: int = 1,
        max_concurrent_video_submit: int = 1,
        poll_interval_sec: float = 4.0,
    ) -> PipelineInput:
        if not isinstance(creative_plan, CreativePlan):
            raise TypeError("creative_plan phải là CreativePlan")
        if not isinstance(subject_lock, SubjectLock):
            raise TypeError("subject_lock phải là SubjectLock")
        references = [
            ref.strip()
            for ref in creative_plan.input.product_reference_urls
            if isinstance(ref, str) and ref.strip()
        ]
        if not references:
            raise ValueError("CreativePlan cần ít nhất một product image reference")
        if not creative_plan.input.goal.strip():
            raise ValueError("CreativePlan.input.goal không được rỗng")
        if not creative_plan.input.platform.strip():
            raise ValueError("CreativePlan.input.platform không được rỗng")
        if creative_plan.input.duration_sec <= 0:
            raise ValueError("CreativePlan.input.duration_sec phải > 0")
        subject_lock.validate()

        script_parts: list[str] = []
        if creative_plan.concept.hook.strip():
            script_parts.append(f"HOOK: {creative_plan.concept.hook.strip()}")
        if creative_plan.script.voiceover.strip():
            script_parts.append(f"VOICEOVER: {creative_plan.script.voiceover.strip()}")
        overlays = [x.strip() for x in creative_plan.script.text_overlays if isinstance(x, str) and x.strip()]
        if overlays:
            script_parts.append("TEXT OVERLAYS: " + " | ".join(overlays))
        if creative_plan.script.cta.strip():
            script_parts.append(f"CTA: {creative_plan.script.cta.strip()}")
        if creative_plan.concept.description.strip():
            script_parts.append(f"CONCEPT: {creative_plan.concept.description.strip()}")

        script_text = "\n".join(script_parts).strip()
        if not script_text:
            raise ValueError("CreativePlan không có script/concept content để đưa vào pipeline")

        style_parts = [
            creative_plan.visual_style.style,
            creative_plan.visual_style.lighting,
            creative_plan.visual_style.camera_style,
            creative_plan.visual_style.mood,
        ]
        if creative_plan.visual_style.color_palette:
            style_parts.append("color palette: " + ", ".join(creative_plan.visual_style.color_palette))
        style_hint = ", ".join(x.strip() for x in style_parts if isinstance(x, str) and x.strip())
        if not style_hint:
            style_hint = "cinematic, natural lighting, photographic"

        subject_name = (
            creative_plan.product.name.strip()
            or creative_plan.product.category.strip()
            or "chủ thể chính"
        )
        character_reference = creative_plan.character.reference_url

        return PipelineInput(
            script_text=script_text,
            style_hint=style_hint,
            subject_name=subject_name,
            reference_image_url=character_reference,
            keep_character_consistent=bool(creative_plan.character.required and character_reference),
            quota_mode=quota_mode,
            max_concurrent_image_requests=max_concurrent_image_requests,
            max_concurrent_video_submit=max_concurrent_video_submit,
            poll_interval_sec=poll_interval_sec,
            output_dir=output_dir,
            product_reference_url=references[0],
            product_reference_urls=references,
            creative_plan=creative_plan,
            subject_lock=subject_lock,
        )
