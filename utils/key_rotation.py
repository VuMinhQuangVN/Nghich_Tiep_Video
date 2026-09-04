"""
utils/key_rotation.py
----------------------
Round-robin key rotation + ADAPTIVE COOLDOWN (throttle), thread-safe /
asyncio-safe.

Bối cảnh: Agnes AI hiện đang free — nghĩa là giới hạn thật sự không phải
"hết quota" mà là SERVER CHỊU TẢI khi request dồn dập. Vì vậy thay vì bắn
request liên tục, class này ép 1 khoảng nghỉ (cooldown) TỐI THIỂU giữa 2 lần
gọi liên tiếp trên CÙNG 1 key — mặc định 3-5 phút — và tự ĐỘNG TĂNG cooldown
lên nếu vẫn còn gặp lỗi (429/503), rồi tự GIẢM dần trở lại mức nền khi ổn
định trở lại (adaptive, không cố định cứng nhắc).

CƠ CHẾ NHIỀU KEY (round-robin thông minh, không phải xoay vòng cứng nhắc):
Mỗi key có đồng hồ cooldown RIÊNG, độc lập với nhau. Khi cần 1 key để
generate, hệ thống quét TẤT CẢ key đang rảnh (đã hết giờ nghỉ) và chọn key
nào "dư giờ nghỉ" nhiều nhất (đã sẵn sàng lâu nhất) — tức là:

  key1 vừa dùng xong -> vào "ghế nghỉ" (cooldown riêng của nó bắt đầu đếm)
  key2 đang rảnh (đã nghỉ đủ từ lần trước) -> được gọi làm việc ngay
  key2 dùng xong -> tới lượt nghỉ, quay lại xét key1/key3/...
  Nếu TẤT CẢ key đều đang nghỉ -> chờ tới khi key gần hết giờ nghỉ nhất sẵn sàng

Nhờ vậy tải được rải đều qua các key liên tục, không có key nào bị bắn 2 lần
liên tiếp trong khi key khác đang rảnh, và pipeline hiếm khi phải đứng chờ
hoàn toàn nếu có từ 2 key trở lên.
"""
from __future__ import annotations

import asyncio
import itertools
import time

from utils.logger import get_logger

log = get_logger(__name__)


class KeyRotator:
    def __init__(
        self,
        keys: list[str],
        cooldown_base_sec: float = 180.0,   # 3 phút — mức nghỉ nền giữa 2 request/key
        cooldown_max_sec: float = 900.0,     # 15 phút — trần trên cùng
        cooldown_step_sec: float = 60.0,     # mỗi lần lỗi, tăng thêm ngần này
        cooldown_decay_after_success: int = 3,  # 3 lần thành công liên tiếp thì giảm cooldown 1 nấc
    ):
        if not keys:
            raise ValueError("KeyRotator cần ít nhất 1 API key")
        self._keys = list(keys)
        self._cycle = itertools.cycle(self._keys)
        self._lock = asyncio.Lock()
        self._bad_keys: set[str] = set()

        self._cooldown_base = cooldown_base_sec
        self._cooldown_max = cooldown_max_sec
        self._cooldown_step = cooldown_step_sec

        # trạng thái điều chỉnh RIÊNG cho từng key
        self._current_cooldown: dict[str, float] = {k: cooldown_base_sec for k in self._keys}
        self._last_used_at: dict[str, float] = {k: 0.0 for k in self._keys}
        self._success_streak: dict[str, int] = {k: 0 for k in self._keys}
        self._decay_after = cooldown_decay_after_success

    async def acquire_key(self) -> str:
        """Chọn 1 key đã đủ thời gian nghỉ (cooldown) để dùng ngay.
        Nếu MỌI key đều đang nghỉ, chờ tới khi key gần hết cooldown nhất sẵn sàng
        (không bắn request trước hạn — đây là điểm khác round-robin thuần)."""
        while True:
            async with self._lock:
                candidate = self._pick_ready_key_locked()
                if candidate is not None:
                    self._last_used_at[candidate] = time.monotonic()
                    return candidate
                wait_for = self._shortest_wait_locked()
            log.info(f"Tất cả key đang trong thời gian nghỉ, chờ thêm {wait_for:.0f}s...")
            await asyncio.sleep(min(wait_for, 30))  # chia nhỏ để có thể log/hủy giữa chừng

    def _pick_ready_key_locked(self) -> str | None:
        """Chọn key TỐI ƯU trong số các key đã đủ cooldown: ưu tiên key nào
        "dư giờ nghỉ" nhiều nhất (đã sẵn sàng lâu nhất), KHÔNG đi vòng tròn
        cứng nhắc — vì mỗi key có thể có cooldown khác nhau (key vừa bị lỗi
        sẽ có cooldown dài hơn key đang ổn định), nên round-robin thuần dễ
        chọn nhầm key chưa thật sự tối ưu.
        """
        now = time.monotonic()
        best_key: str | None = None
        best_slack = -1.0  # elapsed - cooldown càng lớn = càng "dư giờ nghỉ", càng nên dùng trước
        for key in self._keys:
            if key in self._bad_keys:
                continue
            elapsed = now - self._last_used_at[key]
            slack = elapsed - self._current_cooldown[key]
            if slack >= 0 and slack > best_slack:
                best_slack = slack
                best_key = key
        return best_key

    def _shortest_wait_locked(self) -> float:
        now = time.monotonic()
        waits = [
            self._current_cooldown[k] - (now - self._last_used_at[k])
            for k in self._keys
            if k not in self._bad_keys
        ]
        return max(0.0, min(waits)) if waits else self._cooldown_base

    async def acquire_key_light(self) -> str:
        """Dùng cho endpoint NHẸ, cần gọi thường xuyên (VD: poll trạng thái
        video) — KHÔNG áp cooldown 3-5 phút, chỉ round-robin đơn thuần, tránh
        làm chậm vòng theo dõi tiến độ. Sinh ảnh/video mới thì dùng
        acquire_key() (có cooldown) — 2 việc này khác nhau về tải lên server."""
        async with self._lock:
            for _ in range(len(self._keys)):
                key = next(self._cycle)
                if key not in self._bad_keys:
                    return key
            self._bad_keys.clear()
            return next(self._cycle)

    # Giữ tương thích ngược với code cũ (không throttle) — không khuyến khích dùng nữa.
    async def next_key(self) -> str:
        return await self.acquire_key()

    async def report_success(self, key: str) -> None:
        """Gọi sau khi request thành công — sau vài lần liên tiếp OK,
        giảm dần cooldown về gần mức nền (nhưng không bao giờ dưới mức nền)."""
        async with self._lock:
            self._success_streak[key] = self._success_streak.get(key, 0) + 1
            if self._success_streak[key] >= self._decay_after:
                old = self._current_cooldown[key]
                new = max(self._cooldown_base, old - self._cooldown_step)
                if new != old:
                    log.info(f"Key ...{key[-4:]} ổn định, giảm cooldown {old:.0f}s -> {new:.0f}s")
                self._current_cooldown[key] = new
                self._success_streak[key] = 0

    async def report_rate_limited(self, key: str) -> None:
        """Gọi khi request bị 429/503 — tăng cooldown của key đó lên (adaptive),
        như yêu cầu: nghỉ 3-5 phút, nếu vẫn chưa ổn thì tăng thêm."""
        async with self._lock:
            self._success_streak[key] = 0
            old = self._current_cooldown[key]
            new = min(self._cooldown_max, old + self._cooldown_step)
            self._current_cooldown[key] = new
            log.warning(f"Key ...{key[-4:]} bị chặn tốc độ, tăng cooldown {old:.0f}s -> {new:.0f}s")

    async def mark_bad(self, key: str) -> None:
        """Gọi khi 1 key trả về 401/403 (invalid hẳn, không phải rate-limit),
        loại khỏi vòng xoay trong phiên chạy hiện tại."""
        async with self._lock:
            self._bad_keys.add(key)

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def current_cooldown_for(self, key: str) -> float:
        return self._current_cooldown.get(key, self._cooldown_base)
