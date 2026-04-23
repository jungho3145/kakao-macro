"""NTP 오프셋을 반영한 정밀 스케줄러.

Windows의 `time.sleep` 해상도는 일반적으로 15.6ms 수준이다. 목표 시각 직전까지는
`time.sleep`으로 대기하고, 마지막 구간은 busy-wait로 전환해 밀리초 수준의 정밀도
를 확보한다.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from .time_sync import TimeOffset

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def parse_kst(dt_str: str) -> float:
    """`YYYY-MM-DD HH:MM:SS[.fff]` 형식의 KST 문자열을 Unix epoch 초로 변환."""
    fmts = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")
    last_err: Exception | None = None
    for fmt in fmts:
        try:
            naive = datetime.strptime(dt_str.strip(), fmt)
            break
        except ValueError as exc:
            last_err = exc
    else:
        raise ValueError(f"시간 형식이 올바르지 않습니다: {dt_str!r} ({last_err})")

    return naive.replace(tzinfo=KST).timestamp()


def sleep_until(target_epoch: float, offset: TimeOffset,
                tick: Callable[[float], None] | None = None,
                busy_wait_window: float = 0.05) -> None:
    """서버 기준 `target_epoch`까지 대기.

    Args:
        target_epoch: 목표 시각 (Unix epoch 초, 서버 기준)
        offset: NTP 오프셋 (서버 시각 = 로컬 + offset.offset_seconds)
        tick: 초 단위로 호출되는 콜백. 인자는 남은 초.
        busy_wait_window: 목표 시각 전까지 busy-wait로 전환할 임계(초).
    """
    last_tick = 0.0
    while True:
        remaining = target_epoch - offset.now()
        if remaining <= 0:
            return

        # busy-wait 구간
        if remaining <= busy_wait_window:
            while offset.now() < target_epoch:
                pass
            return

        # 1초 단위 tick 콜백
        if tick is not None and remaining - int(remaining) < 0.05:
            sec = int(remaining)
            if sec != last_tick:
                tick(float(sec))
                last_tick = sec

        # 긴 대기: 남은 시간의 절반씩 깎거나, 최대 1초 단위
        sleep_for = min(1.0, max(0.01, remaining - busy_wait_window))
        time.sleep(sleep_for)
