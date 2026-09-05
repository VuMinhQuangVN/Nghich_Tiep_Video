import pytest

from core.product_analyzer import ProductAnalyzer


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def analyze_image(self, image_path_or_url, question):
        self.calls.append((image_path_or_url, question))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_analyze_single_product():
    engine = FakeEngine([
        '{"name":"Serum X","category":"skincare","description":"Chai serum màu trắng",'
        '"visual_identity":"chai trắng, nhãn xanh",'
        '"selling_points":["thiết kế tối giản"],'
        '"consistency_requirements":["giữ nguyên logo và màu chai"]}'
    ])

    profile = await ProductAnalyzer(engine).analyze(["https://example.com/product.jpg"])

    assert profile.name == "Serum X"
    assert profile.category == "skincare"
    assert profile.visual_identity == "chai trắng, nhãn xanh"
    assert profile.selling_points == ["thiết kế tối giản"]
    assert profile.consistency_requirements == ["giữ nguyên logo và màu chai"]
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_analyze_multiple_references_merges_lists():
    engine = FakeEngine([
        '{"name":"Shoe A","category":"shoes","description":"Giày màu đen",'
        '"visual_identity":"đen, đế trắng",'
        '"selling_points":["form thấp","đế trắng"],'
        '"consistency_requirements":["logo bên hông"]}',
        '{"name":"Shoe A","category":"shoes","description":"Góc nghiêng của giày",'
        '"visual_identity":"đen, đế trắng",'
        '"selling_points":["đế trắng","dây giày đen"],'
        '"consistency_requirements":["logo bên hông","không đổi màu đế"]}'
    ])

    profile = await ProductAnalyzer(engine).analyze([
        "https://example.com/front.jpg",
        "https://example.com/side.jpg",
    ])

    assert profile.name == "Shoe A"
    assert profile.description == "Giày màu đen Góc nghiêng của giày"
    assert profile.selling_points == ["form thấp", "đế trắng", "dây giày đen"]
    assert profile.consistency_requirements == [
        "logo bên hông",
        "không đổi màu đế",
    ]
    assert len(engine.calls) == 2


def test_parse_markdown_json():
    raw = '```json\n{"name":"Test","category":"bag"}\n```'
    parsed = ProductAnalyzer._parse_response(raw)

    assert parsed["name"] == "Test"
    assert parsed["category"] == "bag"


def test_parse_json_with_surrounding_text():
    raw = 'Kết quả phân tích:\n{"name":"Test","category":"bag"}\nHết.'
    parsed = ProductAnalyzer._parse_response(raw)

    assert parsed == {"name": "Test", "category": "bag"}


@pytest.mark.asyncio
async def test_empty_references_are_rejected():
    engine = FakeEngine([])

    with pytest.raises(ValueError, match="ít nhất một"):
        await ProductAnalyzer(engine).analyze(["", "   ", None])


def test_non_json_response_has_safe_fallback():
    parsed = ProductAnalyzer._parse_response("Sản phẩm màu đỏ, dạng chai.")
    assert parsed["description"] == "Sản phẩm màu đỏ, dạng chai."
