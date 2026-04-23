"""마우스 좌표 캡처 도구.

사용자는 실제 카카오톡 화면에서 댓글 입력창 위치를 한 번 캡처해 설정한다.
F9 키로 현재 마우스 좌표를 저장하고, Esc로 종료한다.
"""
from __future__ import annotations

import logging
import time

import pyautogui

logger = logging.getLogger(__name__)


def capture_once(hotkey: str = "f9", stop_key: str = "esc") -> tuple[int, int] | None:
    """핫키를 한 번 누를 때까지 대기한 뒤 해당 시점의 마우스 좌표 반환.

    keyboard 모듈은 Windows에서 전역 훅을 걸 수 있어 다른 창이 포커스된 상태에서도
    동작한다. macOS/Linux에서는 권한 문제로 동작이 제한될 수 있다.
    """
    try:
        import keyboard  # type: ignore
    except ImportError as exc:
        raise RuntimeError("keyboard 모듈을 설치하세요: pip install keyboard") from exc

    print(f"[캡처] 카카오톡에서 원하는 위치에 마우스를 올리고 [{hotkey.upper()}] 키를 누르세요.")
    print(f"       취소는 [{stop_key.upper()}].")

    captured: dict[str, tuple[int, int] | None] = {"pos": None}
    done = {"flag": False}

    def on_capture() -> None:
        pos = pyautogui.position()
        captured["pos"] = (int(pos.x), int(pos.y))
        print(f"   ✓ 좌표 저장: ({pos.x}, {pos.y})")
        done["flag"] = True

    def on_stop() -> None:
        print("   ✗ 사용자 취소")
        done["flag"] = True

    keyboard.add_hotkey(hotkey, on_capture)
    keyboard.add_hotkey(stop_key, on_stop)

    try:
        while not done["flag"]:
            time.sleep(0.05)
    finally:
        keyboard.clear_all_hotkeys()

    return captured["pos"]
