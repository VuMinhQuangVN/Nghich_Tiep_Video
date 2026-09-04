"""
core/prompt_composer.py
--------------------------
Chứa các template prompt lấy Y NGUYÊN tinh thần từ knowledge-base/techniques/*.md
và knowledge-base/character-lock.md, chỉ tham số hoá bằng dữ liệu scene thực tế.
Tách riêng khỏi logic gọi API (SRP) — file này KHÔNG gọi network.
"""
from __future__ import annotations


def character_sheet_prompt(subject_description: str, style: str, num_angles: int = 4) -> str:
    return (
        f"Character reference sheet, {num_angles} turnaround angles: front view, "
        f"3/4 left, 3/4 right, back view, close-up on face/key detail.\n"
        f"Subject: {subject_description}.\n"
        f"Style: {style}.\n"
        f"Consistent lighting, neutral background, same subject across all angles, "
        f"high detail, production-ready reference sheet."
    )


def scene_image_prompt(scene_description: str, style: str, mood: str = "") -> str:
    return (
        f"{scene_description}, subject consistent with reference image, "
        f"style: {style}, {mood}."
    )


def keyframe_image_prompt(moment_description: str, style: str) -> str:
    return (
        f"{moment_description}, subject consistent with reference image, "
        f"style: {style}."
    )


def keyframe_video_prompt(subject_name: str, mood: str = "") -> str:
    return (
        f"Generate a smooth cinematic transition through these keyframes in order, "
        f"maintaining {subject_name} identity, consistent camera angle logic, "
        f"and natural motion between each keyframe. {mood}."
    )


def scene_video_prompt(action_desc: str, camera_move: str, mood: str, duration_sec: float) -> str:
    return (
        f"{action_desc}, camera: {camera_move}, mood: {mood}, "
        f"duration {duration_sec:.0f}s. "
        f"Maintain exact subject appearance and style from the reference image."
    )


def single_shot_video_prompt(action_desc: str, camera_move: str, mood: str, duration_sec: float) -> str:
    return f"{action_desc}, camera: {camera_move}, mood: {mood}, duration {duration_sec:.0f}s."
