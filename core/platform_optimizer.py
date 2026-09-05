"""Phase 12: deterministic platform optimization guidance.

This module does not generate creative content and does not call an LLM.  It
provides a small, testable platform contract that the Creative Director and
Scene Planner include in their prompts.  The LLM remains responsible for the
actual creative choices; this layer makes the platform requirements explicit
and consistent across planners.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    hook_window: str
    pacing: str
    text_guidance: str
    cta_guidance: str
    shot_duration: str
    story_structure: str


_PROFILES = {
    "tiktok": PlatformProfile(
        name="TikTok",
        hook_window="0-3s",
        pacing="fast; change visual information frequently and avoid a slow intro",
        text_guidance="short, high-signal on-screen text; readable immediately on mobile",
        cta_guidance="clear, direct CTA at the end; reserve the final beat for conversion",
        shot_duration="prefer short shots, generally about 1-4s, with longer shots only when the demonstration needs it",
        story_structure="0-3s strong hook; 3-20s product demonstration; 20-27s benefit; 27-30s CTA when duration is 30s",
    ),
    "instagram_reels": PlatformProfile(
        name="Instagram Reels",
        hook_window="0-3s",
        pacing="fast-to-medium; keep a polished visual rhythm and front-load the product",
        text_guidance="minimal, clean overlays that preserve a premium mobile composition",
        cta_guidance="concise CTA near the final beat, aligned with discovery or purchase intent",
        shot_duration="prefer roughly 1-5s shots; use rhythm changes without making the edit feel chaotic",
        story_structure="hook; visual product reveal/demo; key benefit; concise CTA",
    ),
    "youtube_shorts": PlatformProfile(
        name="YouTube Shorts",
        hook_window="0-3s",
        pacing="fast and information-dense; establish context quickly and sustain momentum",
        text_guidance="high-legibility text that supports the spoken/visual message rather than duplicating it excessively",
        cta_guidance="clear final CTA, with enough context for the viewer to understand the next action",
        shot_duration="prefer roughly 1-5s shots, allowing slightly longer explanatory beats when useful",
        story_structure="hook; setup/problem; product demonstration; benefit/proof; CTA",
    ),
    "facebook": PlatformProfile(
        name="Facebook",
        hook_window="0-3s",
        pacing="medium; make the value proposition understandable quickly while allowing product context",
        text_guidance="strong captions/overlays for silent viewing; keep wording concise and legible",
        cta_guidance="explicit CTA tied to the video's objective, especially for conversion-oriented content",
        shot_duration="prefer roughly 2-6s shots, using longer beats when they improve comprehension",
        story_structure="hook; context/problem; product demonstration; benefit; CTA",
    ),
}

_ALIASES = {
    "instagram reels": "instagram_reels",
    "instagram_reel": "instagram_reels",
    "reels": "instagram_reels",
    "youtube shorts": "youtube_shorts",
    "youtube_short": "youtube_shorts",
    "shorts": "youtube_shorts",
    "facebook": "facebook",
    "tiktok": "tiktok",
}


def normalize_platform(value: str) -> str:
    """Return the canonical platform key or raise for unsupported platforms."""
    key = "_".join((value or "").strip().lower().split())
    key = _ALIASES.get(key, key)
    if key not in _PROFILES:
        supported = ", ".join(profile.name for profile in _PROFILES.values())
        raise ValueError(f"Unsupported platform {value!r}; supported platforms: {supported}")
    return key


def get_platform_profile(value: str) -> PlatformProfile:
    return _PROFILES[normalize_platform(value)]


def build_platform_guidance(value: str) -> str:
    """Build concise instructions for LLM planners from the platform contract."""
    profile = get_platform_profile(value)
    return (
        f"PLATFORM OPTIMIZATION — {profile.name}\n"
        f"Hook window: {profile.hook_window}\n"
        f"Pacing: {profile.pacing}\n"
        f"Text: {profile.text_guidance}\n"
        f"CTA: {profile.cta_guidance}\n"
        f"Shot duration: {profile.shot_duration}\n"
        f"Story structure: {profile.story_structure}"
    )
