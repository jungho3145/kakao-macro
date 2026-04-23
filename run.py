"""카카오톡 공지 댓글 매크로 — 엔트리 포인트.

서브커맨드:
  capture   좌표 캡처 대화형 도구 실행
  run       설정 파일을 읽고 목표 시각에 댓글 게시
  dry-run   실제 클릭/입력 없이 동작만 로그로 출력
  now       NTP 동기화 후 서버 기준 현재 시각 표시
  gui       Tkinter GUI 실행
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.config import MacroConfig
from src.kakao_automation import CommentPlan, execute_plan, focus_kakao_window
from src.scheduler import parse_kst, sleep_until
from src.time_sync import fetch_offset

DEFAULT_CONFIG_PATH = Path("config.json")
KST = timezone(timedelta(hours=9))


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_kst(ts_epoch: float, label: str) -> None:
    dt = datetime.fromtimestamp(ts_epoch, tz=KST)
    print(f"  {label}: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} KST")


def cmd_now(_: argparse.Namespace) -> int:
    offset = fetch_offset()
    _print_kst(offset.now(), "서버(NTP) 현재")
    _print_kst(time.time(), "로컬 현재    ")
    print(f"  오프셋: {offset.offset_seconds*1000:+.1f} ms (server={offset.server}, rtt={offset.rtt_seconds*1000:.1f} ms)")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    from src.position_capture import capture_once

    cfg_path = Path(args.config)
    cfg = MacroConfig.load(cfg_path) if cfg_path.exists() else MacroConfig()

    n = int(args.count)
    print(f"[캡처] {n}개의 좌표를 순서대로 캡처합니다.")
    print("  ex) 1번: 공지 목록 열기, 2번: 특정 공지 선택, 3번: 댓글 입력창 클릭")
    print("  이미 공지 화면을 열어두었다면 1번(댓글 입력창)만 캡처해도 됩니다.\n")

    positions: list[tuple[int, int]] = []
    for idx in range(1, n + 1):
        print(f"── {idx}/{n}번 좌표 ──")
        pos = capture_once()
        if pos is None:
            print("취소됨.")
            return 1
        positions.append(pos)

    cfg.click_positions = positions
    cfg.save(cfg_path)
    print(f"\n저장 완료 → {cfg_path}")
    print(json.dumps({"click_positions": positions}, ensure_ascii=False, indent=2))
    return 0


def _build_plan(cfg: MacroConfig) -> CommentPlan:
    if not cfg.click_positions:
        raise SystemExit("설정의 click_positions가 비어 있습니다. 먼저 `capture`로 좌표를 저장하세요.")
    if not cfg.comment_text.strip():
        raise SystemExit("설정의 comment_text가 비어 있습니다.")
    return CommentPlan(
        click_positions=cfg.click_positions,
        comment_text=cfg.comment_text,
        step_delay_seconds=cfg.step_delay_seconds,
        submit_with_enter=cfg.submit_with_enter,
    )


def _run_common(cfg: MacroConfig, *, dry_run: bool, no_wait: bool) -> int:
    plan = _build_plan(cfg)

    if no_wait:
        focus_kakao_window(cfg.window_title_contains)
        execute_plan(plan, dry_run=dry_run)
        return 0

    if not cfg.target_time_kst:
        raise SystemExit("target_time_kst가 비어 있습니다. 예: '2026-04-23 20:00:00'")

    offset = fetch_offset()
    target_epoch = parse_kst(cfg.target_time_kst)

    remaining = target_epoch - offset.now()
    if remaining < 0:
        raise SystemExit(f"목표 시각이 이미 지났습니다 (남은 시간 {remaining:.1f}s)")

    print(f"[대기] 목표 {cfg.target_time_kst} KST까지 {remaining:.1f}초 남음")
    print(f"       NTP 오프셋 {offset.offset_seconds*1000:+.1f}ms (server={offset.server})")

    def tick(sec: float) -> None:
        if sec <= 10 or int(sec) % 10 == 0:
            sys.stdout.write(f"\r  남은 시간: {int(sec):>4}s ")
            sys.stdout.flush()

    # 5초 전 창 포커싱
    pre_focus_epoch = target_epoch - 5.0
    if offset.now() < pre_focus_epoch:
        sleep_until(pre_focus_epoch, offset, tick=tick)
    print()
    focus_kakao_window(cfg.window_title_contains)

    # 나머지 대기 (고정밀)
    sleep_until(target_epoch, offset)
    print(f"[실행] {datetime.fromtimestamp(offset.now(), tz=KST).strftime('%H:%M:%S.%f')[:-3]} KST")
    execute_plan(plan, dry_run=dry_run)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = MacroConfig.load(Path(args.config))
    return _run_common(cfg, dry_run=False, no_wait=args.no_wait)


def cmd_dry_run(args: argparse.Namespace) -> int:
    cfg = MacroConfig.load(Path(args.config))
    return _run_common(cfg, dry_run=True, no_wait=args.no_wait)


def cmd_gui(_: argparse.Namespace) -> int:
    from src.gui import launch
    launch()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="kakao-macro", description="카카오톡 공지 댓글 매크로")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-c", "--config", default=str(DEFAULT_CONFIG_PATH), help="설정 파일 경로")

    sub = parser.add_subparsers(dest="command", required=True)

    p_capture = sub.add_parser("capture", help="좌표 캡처")
    p_capture.add_argument("-n", "--count", default=3, help="캡처할 좌표 개수 (기본 3)")
    p_capture.set_defaults(func=cmd_capture)

    p_run = sub.add_parser("run", help="목표 시각에 실제 실행")
    p_run.add_argument("--no-wait", action="store_true", help="시간 대기 없이 즉시 실행")
    p_run.set_defaults(func=cmd_run)

    p_dry = sub.add_parser("dry-run", help="리허설 (실제 입력 없음)")
    p_dry.add_argument("--no-wait", action="store_true", help="시간 대기 없이 즉시 실행")
    p_dry.set_defaults(func=cmd_dry_run)

    p_now = sub.add_parser("now", help="서버 시간 확인")
    p_now.set_defaults(func=cmd_now)

    p_gui = sub.add_parser("gui", help="Tkinter GUI 실행")
    p_gui.set_defaults(func=cmd_gui)

    args = parser.parse_args()
    _setup_logging(args.verbose)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n중단됨.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
