"""한국 NTP 서버 기반 시간 동기화.

카카오톡 서버는 공개 시간 API를 제공하지 않는다. 카카오 서버는 한국 표준시(KST,
UTC+9)를 사용하며 최상위 시각원은 KRISS(한국표준과학연구원)다. 따라서 국내 NTP
서버와의 오프셋이 카카오 서버 시간에 가장 근접한 프록시다.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import ntplib

logger = logging.getLogger(__name__)

# 한국 내 공개 NTP 서버. 상단이 우선순위.
KR_NTP_SERVERS = (
    "time.bora.net",
    "kr.pool.ntp.org",
    "time.kriss.re.kr",
    "time.google.com",
)


@dataclass(frozen=True)
class TimeOffset:
    """NTP 서버와 로컬 시계의 차이.

    server_time ≈ local_time + offset_seconds
    """

    offset_seconds: float
    rtt_seconds: float
    server: str

    def now(self) -> float:
        """오프셋을 적용한 현재 시각(Unix epoch 초, 소수점 포함)."""
        return time.time() + self.offset_seconds


def fetch_offset(timeout: float = 3.0) -> TimeOffset:
    """NTP 서버 목록을 순회하며 첫 번째 성공 응답으로 오프셋을 계산한다.

    ntplib의 `offset`은 이미 RTT 보정이 적용된 로컬 시계 보정값이다.
    """
    client = ntplib.NTPClient()
    last_error: Exception | None = None

    for server in KR_NTP_SERVERS:
        try:
            response = client.request(server, version=3, timeout=timeout)
            offset = TimeOffset(
                offset_seconds=response.offset,
                rtt_seconds=response.delay,
                server=server,
            )
            logger.info(
                "NTP sync ok: server=%s offset=%+.3fms rtt=%.1fms",
                server,
                offset.offset_seconds * 1000.0,
                offset.rtt_seconds * 1000.0,
            )
            return offset
        except Exception as exc:  # noqa: BLE001 — 서버별로 네트워크 오류가 다양함
            last_error = exc
            logger.warning("NTP sync failed on %s: %s", server, exc)
            continue

    raise RuntimeError(f"모든 NTP 서버 동기화 실패: {last_error!r}")
