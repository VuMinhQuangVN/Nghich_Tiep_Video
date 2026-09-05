import pytest

from core.platform_optimizer import build_platform_guidance, get_platform_profile, normalize_platform


def test_supported_platforms_have_complete_contract():
    for platform in ("TikTok", "Instagram Reels", "YouTube Shorts", "Facebook"):
        profile = get_platform_profile(platform)
        assert profile.name
        assert profile.hook_window
        assert profile.pacing
        assert profile.text_guidance
        assert profile.cta_guidance
        assert profile.shot_duration
        assert profile.story_structure


def test_platform_aliases_normalize():
    assert normalize_platform("TikTok") == "tiktok"
    assert normalize_platform("Instagram Reels") == "instagram_reels"
    assert normalize_platform("youtube shorts") == "youtube_shorts"
    assert normalize_platform("Facebook") == "facebook"


def test_unsupported_platform_rejected():
    with pytest.raises(ValueError, match="Unsupported platform"):
        normalize_platform("LinkedIn")


def test_tiktok_guidance_contains_roadmap_structure():
    guidance = build_platform_guidance("TikTok")
    assert "0-3s" in guidance
    assert "3-20s" in guidance
    assert "20-27s" in guidance
    assert "27-30s" in guidance
    assert "Strong hook" not in guidance  # contract is descriptive, not copied verbatim
    assert "Shot duration" in guidance


def test_director_prompt_includes_platform_guidance():
    from core.creative_director import CreativeDirector
    from models.creative_plan import CreativeInput, ProductProfile

    plan_input = CreativeInput(["https://example.com/p.jpg"], "sell", "TikTok", 30)
    product = ProductProfile(name="Product")
    prompt = CreativeDirector(None)._build_prompt(plan_input, product)
    assert "PLATFORM OPTIMIZATION — TikTok" in prompt
    assert "Hook window: 0-3s" in prompt
    assert "Shot duration:" in prompt


def test_scene_prompt_includes_platform_guidance():
    from core.scene_planner import ScenePlanner
    from models.creative_plan import CreativeInput, CreativePlan, CreativeScene, ProductProfile
    from models.subject_lock import SubjectLock

    plan = CreativePlan(
        input=CreativeInput(["https://example.com/p.jpg"], "sell", "TikTok", 30),
        product=ProductProfile(name="Product"),
        scenes=[CreativeScene(1, objective="hook", description="product", product_visibility="full")],
    )
    lock = SubjectLock(
        reference_urls=["https://example.com/p.jpg"],
        identity_features=["Product"],
        invariants=["keep product unchanged"],
        character_required=False,
    )
    prompt = ScenePlanner._build_prompt(plan, lock)
    assert "PLATFORM OPTIMIZATION — TikTok" in prompt
    assert "Story structure:" in prompt
