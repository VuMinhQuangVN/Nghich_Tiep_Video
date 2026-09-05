import pytest
from core.creative_director import CreativeDirector
from models.creative_plan import CreativeInput, ProductProfile

class FakeEngine:
    def __init__(self, response): self.response = response; self.calls = []
    async def analyze_image(self, url, question): self.calls.append((url, question)); return self.response

def product():
    return ProductProfile("Serum X", "skincare", "Chai serum màu trắng", ["chai trắng", "nhãn xanh"], ["thiết kế tối giản"], ["giữ nguyên logo"])

def inp():
    return CreativeInput(["https://example.com/serum.jpg"], "Tăng nhận diện và thúc đẩy mua hàng", "TikTok", 15, "vi")

RESPONSE = '''{"audience":{"age_range":"18-30","gender":"female","interests":["skincare"],"pain_points":["khó chọn serum"]},"concept":{"title":"Một giây nhận ra","description":"Reveal nhanh sản phẩm","hook":"Bạn có 3 giây?"},"visual_style":{"style":"premium clean beauty","lighting":"soft studio","color_palette":["white","blue"],"camera_style":"macro product shots","mood":"fresh"},"character":{"required":false,"description":"","reference_url":null},"script":{"voiceover":"Đây là Serum X.","text_overlays":["Clean beauty"],"cta":"Khám phá ngay"}}'''

@pytest.mark.asyncio
async def test_direct_builds_plan():
    e = FakeEngine(RESPONSE); plan = await CreativeDirector(e).direct(inp(), product())
    assert plan.concept.title == "Một giây nhận ra"; assert plan.audience.age_range == "18-30"
    assert plan.visual_style.style == "premium clean beauty"; assert not plan.character.required
    assert plan.script.cta == "Khám phá ngay"; assert plan.scenes == []; assert len(e.calls) == 1

@pytest.mark.asyncio
async def test_required_character_needs_description():
    e = FakeEngine('{"character":{"required":true,"description":""}}')
    with pytest.raises(ValueError, match="character as required"): await CreativeDirector(e).direct(inp(), product())

@pytest.mark.asyncio
async def test_invalid_json_rejected():
    with pytest.raises(ValueError, match="valid JSON"): await CreativeDirector(FakeEngine("bad")).direct(inp(), product())

@pytest.mark.asyncio
async def test_input_validated_before_engine_call():
    e = FakeEngine("{}"); bad = CreativeInput([], "", "TikTok", 15)
    with pytest.raises(ValueError, match="product reference URLs"): await CreativeDirector(e).direct(bad, product())
    assert e.calls == []

def test_prompt_contains_context():
    p = CreativeDirector(FakeEngine("{}"))._build_prompt(inp(), product())
    assert "Tăng nhận diện" in p and "TikTok" in p and "Serum X" in p and "giữ nguyên logo" in p
