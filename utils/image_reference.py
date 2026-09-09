"""Utilities for turning browser-uploaded product images into compact Agnes references."""
from __future__ import annotations

import base64
from io import BytesIO

from fastapi import UploadFile

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
# Keep inline vision references comfortably below the text-model context limit.
# Base64 expands binary data by ~4/3, so 300 KB of JPEG is still only ~400 KB of
# text before tokenization. This is deliberately much smaller than the 524K limit.
MAX_AI_REFERENCE_BYTES = 300 * 1024
MAX_AI_REFERENCE_DIMENSION = 1280


def _compact_image_bytes(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Resize/re-encode an uploaded image to a bounded JPEG for vision APIs.

    Agnes' OpenAI-compatible vision endpoint receives ``image_url.url``. A raw
    multi-megabyte Data URI is tokenized by the upstream gateway and can exceed
    the text model context window. A bounded JPEG preserves the visual content
    needed for product analysis while preventing that failure mode.
    """
    if len(data) <= MAX_AI_REFERENCE_BYTES:
        return data, content_type

    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_AI_REFERENCE_DIMENSION, MAX_AI_REFERENCE_DIMENSION), Image.Resampling.LANCZOS)

            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            quality = 72
            encoded = b""
            while quality >= 40:
                out = BytesIO()
                image.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
                encoded = out.getvalue()
                if len(encoded) <= MAX_AI_REFERENCE_BYTES:
                    break
                quality -= 8

            # If an unusually detailed image is still too large, shrink once more.
            while len(encoded) > MAX_AI_REFERENCE_BYTES and max(image.size) > 640:
                new_size = tuple(max(1, int(v * 0.8)) for v in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                out = BytesIO()
                image.save(out, format="JPEG", quality=50, optimize=True, progressive=True)
                encoded = out.getvalue()

            if len(encoded) <= MAX_AI_REFERENCE_BYTES:
                return encoded, "image/jpeg"
    except Exception:
        # Do not make uploads fail merely because an optional image codec is
        # unavailable. The dependency is declared in requirements.txt, but a
        # malformed/unsupported image should still reach the existing API error.
        pass

    raise ValueError(
        "Ảnh upload quá lớn để gửi tới AI. Hãy cài Pillow hoặc giảm kích thước ảnh rồi thử lại."
    )


async def upload_to_data_uri(upload: UploadFile) -> str:
    """Validate an uploaded product image and return a compact Agnes Data URI."""
    content_type = (upload.content_type or "").lower().strip()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Ảnh sản phẩm phải là JPEG, PNG hoặc WebP")

    data = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if len(data) > MAX_PRODUCT_IMAGE_BYTES:
        raise ValueError("Ảnh sản phẩm không được vượt quá 10 MB")
    if not data:
        raise ValueError("Ảnh sản phẩm upload đang rỗng")

    compact_data, compact_type = _compact_image_bytes(data, content_type)
    encoded = base64.b64encode(compact_data).decode("ascii")
    return f"data:{compact_type};base64,{encoded}"
