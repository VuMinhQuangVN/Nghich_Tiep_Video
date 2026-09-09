"""
core/subject_lock.py
---------------------
Giữ danh sách reference images để truyền vào gen ảnh/video.
Đơn giản hóa: không cần "lock contract" phức tạp.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SubjectLock:
    """Reference images dùng xuyên suốt pipeline."""
    reference_urls: list[str] = field(default_factory=list)


class SubjectLockBuilder:
    def build(
        self,
        product_reference_urls: list[str],
        style_reference_urls: list[str] | None = None,
        product: dict | None = None,
        character: dict | None = None,
    ) -> SubjectLock:
        refs = list(product_reference_urls)
        for url in (style_reference_urls or []):
            if url and url not in refs:
                refs.append(url)
        return SubjectLock(reference_urls=refs)
