"""Utilities for turning browser-uploaded product images into Agnes references."""
from __future__ import annotations

import base64

from fastapi import UploadFile

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024


async def upload_to_data_uri(upload: UploadFile) -> str:
    """Validate an uploaded product image and return an Agnes-compatible Data URI."""
    content_type = (upload.content_type or "").lower().strip()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Ảnh sản phẩm phải là JPEG, PNG hoặc WebP")

    data = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if len(data) > MAX_PRODUCT_IMAGE_BYTES:
        raise ValueError("Ảnh sản phẩm không được vượt quá 10 MB")
    if not data:
        raise ValueError("Ảnh sản phẩm upload đang rỗng")

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
