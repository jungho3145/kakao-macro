"""카카오톡 데스크톱 창 자동화.

공지 댓글 입력창은 커스텀 렌더링이라 UI Automation 트리로 식별하기 어렵다.
따라서 사용자가 사전에 캡처한 좌표를 클릭 → 클립보드 붙여넣기 → Enter 순으로
동작한다. 한글은 직접 타이핑 시 IME에 의해 깨지므로 반드시 클립보드를 거친다.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pyautogui
import pyperclip

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True  # 좌상단(0,0)으로 마우스 이동 시 중단
pyautogui.PAUSE = 0.0       # 전역 딜레이 제거 (세밀한 제어는 함수에서 수행)


@dataclass
class CommentPlan:
    """공지 댓글 실행 계획.

    click_positions: 순차적으로 클릭할 좌표 목록 (붙여넣기 직전까지의 이동).
        보통 [공지 목록 열기, 특정 공지 선택, 댓글 입력창] 3단계지만,
        공지를 이미 연 상태라면 [댓글 입력창] 한 단계로 충분.
    comment_text: 댓글 본문 (UTF-8 한글 허용)
    step_delay_seconds: 클릭 사이 딜레이 (UI 렌더링 대기)
    submit_button_position: 등록 버튼 좌표. 설정되어 있으면 붙여넣기 후 이 좌표
        를 클릭한다. 카카오톡 공지 댓글은 Enter로 전송되지 않으므로 일반적으로
        이 값을 채워야 한다.
    submit_with_enter: 등록 버튼 좌표가 비어 있을 때 사용할 키 폴백.
        True면 Enter, False면 Ctrl+Enter.
    """

    click_positions: list[tuple[int, int]]
    comment_text: str
    step_delay_seconds: float = 0.25
    submit_button_position: tuple[int, int] | None = None
    submit_with_enter: bool = True


def focus_kakao_window(window_title_contains: str = "카카오톡") -> bool:
    """카카오톡 창을 전면으로 가져온다.

    여러 창이 열려 있으면 첫 매치를 선택한다. 실패해도 좌표 클릭은 동작할 수
    있으므로 bool 반환만 한다.
    """
    try:
        import pygetwindow as gw  # type: ignore
    except ImportError:
        logger.warning("pygetwindow 미설치 — 창 포커싱 스킵")
        return False

    candidates = [w for w in gw.getAllWindows() if window_title_contains in (w.title or "")]
    if not candidates:
        logger.warning("카카오톡 창을 찾지 못했습니다 (title contains=%r)", window_title_contains)
        return False

    win = candidates[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.15)
        logger.info("카카오톡 창 활성화: %r", win.title)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("창 활성화 실패: %s", exc)
        return False


def _click(pos: tuple[int, int]) -> None:
    x, y = pos
    pyautogui.moveTo(x, y, duration=0.05)
    pyautogui.click()


def _paste_text(text: str) -> None:
    """클립보드에 복사 후 Ctrl+V로 붙여넣기."""
    # 기존 클립보드 보존
    previous = None
    try:
        previous = pyperclip.paste()
    except Exception:  # noqa: BLE001
        pass

    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.05)

    # 클립보드 복구 (베스트 에포트)
    if previous is not None:
        try:
            pyperclip.copy(previous)
        except Exception:  # noqa: BLE001
            pass


def execute_plan(plan: CommentPlan, *, dry_run: bool = False) -> None:
    """`CommentPlan`을 실제로 실행한다.

    dry_run=True면 동작을 로그만 남기고 실제 입력은 하지 않는다 (리허설용).
    """
    logger.info(
        "실행 시작: clicks=%d, text_len=%d, dry_run=%s",
        len(plan.click_positions), len(plan.comment_text), dry_run,
    )

    for idx, pos in enumerate(plan.click_positions, 1):
        logger.info("  [%d/%d] click %s", idx, len(plan.click_positions), pos)
        if not dry_run:
            _click(pos)
            time.sleep(plan.step_delay_seconds)

    logger.info("  paste text (%d chars)", len(plan.comment_text))
    if not dry_run:
        _paste_text(plan.comment_text)
        time.sleep(0.05)

    # 카톡 공지 댓글은 Enter로 전송되지 않으므로 등록 버튼 클릭이 정석.
    # submit_button_position이 비어 있을 때만 키 입력 폴백 사용.
    if plan.submit_button_position is not None:
        logger.info("  submit via button click %s", plan.submit_button_position)
        if not dry_run:
            # 붙여넣기 직후 UI가 입력 상태로 전환되는 데 약간의 시간이 필요
            time.sleep(plan.step_delay_seconds)
            _click(plan.submit_button_position)
    elif plan.submit_with_enter:
        logger.info("  submit via Enter (fallback — set submit_button_position to click the 등록 button)")
        if not dry_run:
            pyautogui.press("enter")
    else:
        logger.info("  submit via Ctrl+Enter (fallback)")
        if not dry_run:
            pyautogui.hotkey("ctrl", "enter")

    logger.info("실행 완료")
