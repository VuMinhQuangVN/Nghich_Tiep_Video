import asyncio
import base64
from io import BytesIO

from fastapi import UploadFile

from models.creative_plan import CreativeInput, CreativePlan
from models.generation_request import GenerationMode, GenerationRequest
from utils.image_reference import MAX_PRODUCT_IMAGE_BYTES, upload_to_data_uri


def test_creative_plan_accepts_image_data_uri():
    ref = "data:image/png;base64," + base64.b64encode(b"fake-image").decode()
    plan = CreativePlan(
        input=CreativeInput(
            product_reference_urls=[ref], goal="sell", platform="tiktok"
        )
    )
    with __import__("pytest").raises(ValueError, match="requires at least one scene"):
        plan.validate()


def test_creative_plan_rejects_plain_local_path():
    plan = CreativePlan(
        input=CreativeInput(
            product_reference_urls=[r"C:\images\shoe.jpg"],
            goal="sell",
            platform="tiktok",
        )
    )
    with __import__("pytest").raises(ValueError, match="Invalid product reference"):
        plan.validate()


def test_upload_to_data_uri():
    upload = UploadFile(
        filename="shoe.png",
        file=BytesIO(b"png-bytes"),
        headers={"content-type": "image/png"},
    )
    uri = asyncio.run(upload_to_data_uri(upload))
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == b"png-bytes"


def test_upload_rejects_non_image():
    upload = UploadFile(
        filename="shoe.txt",
        file=BytesIO(b"text"),
        headers={"content-type": "text/plain"},
    )
    with __import__("pytest").raises(ValueError, match="JPEG, PNG hoặc WebP"):
        asyncio.run(upload_to_data_uri(upload))


def test_upload_rejects_oversized_image():
    upload = UploadFile(
        filename="huge.png",
        file=BytesIO(b"x" * (MAX_PRODUCT_IMAGE_BYTES + 1)),
        headers={"content-type": "image/png"},
    )
    with __import__("pytest").raises(ValueError, match="10 MB"):
        asyncio.run(upload_to_data_uri(upload))


def test_generation_request_accepts_data_uri():
    ref = "data:image/webp;base64," + base64.b64encode(b"fake-image").decode()
    request = GenerationRequest(
        mode=GenerationMode.SIMPLE,
        product_reference_url=ref,
        goal="sell",
        platform="tiktok",
        duration_sec=15,
    )
    request.validate()
