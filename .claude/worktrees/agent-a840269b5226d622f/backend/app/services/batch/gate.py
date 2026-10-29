"""Cổng chặn nhịp gọi Gemini — nguyên tử, dùng chung cho MỌI worker (M9).

Vì sao không dùng `rate_limit` của Celery: nó giới hạn theo **từng worker instance**, không phải
toàn hệ thống. Hai worker cùng đặt 10 lượt/phút là thành 20 lượt/phút đập vào provider. Đã kiểm:
Celery 5.4.0 vẫn vậy.

Vì sao không xoay API key: M5 đã đo và ghi lại — Gemini tính hạn mức theo **project**, không theo
key. Nhiều key cùng một project **không** làm tăng quota, chỉ tạo ảo giác là có xoay xở.
Hết quota thì phải báo `blocked_quota` cho đúng sự thật.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: Cửa sổ trượt bằng Lua để TOÀN BỘ phép kiểm-rồi-ghi diễn ra nguyên tử trong Redis.
#: Làm bằng GET rồi INCR ở phía Python thì hai worker cùng đọc "còn 1 lượt" và cùng đi qua.
_LUA_CUA_SO_TRUOT = """
local khoa = KEYS[1]
local bay_gio = tonumber(ARGV[1])
local cua_so = tonumber(ARGV[2])
local gioi_han = tonumber(ARGV[3])
local so_luot = tonumber(ARGV[4])
local dinh_danh = ARGV[5]

redis.call('ZREMRANGEBYSCORE', khoa, 0, bay_gio - cua_so)
local dang_dung = redis.call('ZCARD', khoa)
if dang_dung + so_luot > gioi_han then
  local cu_nhat = redis.call('ZRANGE', khoa, 0, 0, 'WITHSCORES')
  local cho = 0
  if cu_nhat[2] then cho = (tonumber(cu_nhat[2]) + cua_so) - bay_gio end
  return {0, gioi_han - dang_dung, cho}
end
for i = 1, so_luot do
  redis.call('ZADD', khoa, bay_gio, dinh_danh .. ':' .. i)
end
redis.call('EXPIRE', khoa, math.ceil(cua_so) + 1)
return {1, gioi_han - dang_dung - so_luot, 0}
"""


@dataclass(frozen=True)
class GateResult:
    cho_phep: bool
    con_lai: int
    #: Còn bao nhiêu giây nữa thì có lượt trống (chỉ có nghĩa khi bị chặn).
    cho_giay: float
    ly_do: str | None = None


class GeminiProjectRateGate:
    """Giữ nhịp gọi trong hạn mức của **project** Gemini, chung cho mọi worker.

    Trạng thái nằm ở Redis và Redis ở đây chỉ lưu ảnh chụp mỗi 60s (AOF tắt — đã kiểm ở audit),
    nên cổng này **không phải nguồn sự thật** của tiến độ mẻ. Mất trạng thái cổng sau khi Redis
    khởi động lại chỉ khiến vài lượt gọi được nới thêm, chứ không làm sai kết quả mẻ — tiến độ
    luôn đọc lại từ `BatchItem` trong Postgres.
    """

    #: Cổng TẮT hẳn khi đặt limit <= 0 — dùng cho môi trường không cần chặn nhịp.
    def __init__(self, redis_url: str, rpm: int, cua_so_giay: float = 60.0, tien_to: str = "mte:gate") -> None:
        self.redis_url = redis_url
        self.rpm = rpm
        self.cua_so_giay = cua_so_giay
        self.tien_to = tien_to
        self._redis = None
        self._lua = None

    @staticmethod
    def khoa_project(*phan: str) -> str:
        """Định danh ổn định cho project provider — **băm**, không bao giờ chứa API key.

        Khoá này đi vào Redis và có thể lộ ra log, nên tuyệt đối không được suy ngược ra key.
        """
        raw = "|".join(p for p in phan if p)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _ket_noi(self):
        if self._redis is None:
            import redis  # import trễ: tiến trình API không cần cổng này

            self._redis = redis.Redis.from_url(self.redis_url)
            self._lua = self._redis.register_script(_LUA_CUA_SO_TRUOT)
        return self._redis

    def acquire(self, project_key: str, request_units: int = 1) -> GateResult:
        """Xin `request_units` lượt gọi. KHÔNG gọi provider khi bị từ chối."""
        if self.rpm <= 0:
            return GateResult(True, -1, 0.0, "cổng tắt (LLM_PROJECT_RPM<=0)")
        try:
            self._ket_noi()
            bay_gio = time.time()
            dinh_danh = f"{bay_gio:.6f}:{id(self)}"
            cho_phep, con_lai, cho = self._lua(
                keys=[f"{self.tien_to}:{project_key}"],
                args=[bay_gio, self.cua_so_giay, self.rpm, request_units, dinh_danh],
            )
        except Exception as exc:  # noqa: BLE001
            # Redis hỏng thì KHÔNG được âm thầm mở cổng (sẽ đập thẳng vào quota provider),
            # cũng không nên chặn cứng cả hệ thống. Báo rõ là cổng không dùng được.
            logger.error("Cổng nhịp không hoạt động (%s: %s) -> từ chối để an toàn", type(exc).__name__, exc)
            return GateResult(False, 0, 5.0, f"gate_unavailable: {type(exc).__name__}")

        if int(cho_phep) == 1:
            return GateResult(True, int(con_lai), 0.0)
        return GateResult(False, int(con_lai), max(float(cho), 0.0), "rate_limited")
