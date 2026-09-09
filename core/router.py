"""
core/router.py
--------------
Chỉ chứa QuotaMode — đủ để job_manager import.
"""
from __future__ import annotations
from enum import Enum


class QuotaMode(str, Enum):
    SAVE = "tiet_kiem"
    NORMAL = "binh_thuong"
