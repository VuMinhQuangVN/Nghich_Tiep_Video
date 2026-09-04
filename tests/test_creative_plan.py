from models.creative_plan import (
    CreativeInput,
    CreativePlan,
    CreativeScene,
)


def valid_plan() -> CreativePlan:
    return CreativePlan(
        input=CreativeInput(
            product_reference_urls=["https://example.com/product.jpg"],
            goal="Video quảng cáo bán hàng",
            platform="TikTok",
            duration_sec=10,
        ),
        scenes=[
            CreativeScene(index=1, description="Product hero", duration_sec=5),
            CreativeScene(index=2, description="Product demo", duration_sec=5),
        ],
    )


def test_valid_plan():
    valid_plan().validate()


def test_to_dict():
    data = valid_plan().to_dict()

    assert data["input"]["platform"] == "TikTok"
    assert data["scenes"][0]["index"] == 1


def test_missing_product_reference_fails():
    plan = valid_plan()
    plan.input.product_reference_urls = []

    try:
        plan.validate()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "product reference URL" in str(exc)


def test_scene_indexes_must_be_sequential():
    plan = valid_plan()
    plan.scenes[1].index = 3

    try:
        plan.validate()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "sequential" in str(exc)
