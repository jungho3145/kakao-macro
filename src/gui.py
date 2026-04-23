"""Tkinter GUI — 좌표 캡처부터 예약 실행까지 한 화면에서 수행.

별도 스레드에서 실행 루프를 돌려 UI를 블록하지 않는다. NTP 동기화와 카운트다운
을 실시간 표시하고, 중단 버튼으로 즉시 취소할 수 있다.
"""
from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import pyautogui

from .config import MacroConfig
from .kakao_automation import CommentPlan, execute_plan, focus_kakao_window
from .scheduler import parse_kst, sleep_until
from .time_sync import TimeOffset, fetch_offset

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

DEFAULT_CONFIG_PATH = Path("config.json")


class MacroApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("카카오톡 공지 댓글 매크로")
        root.geometry("560x640")

        self.cfg = MacroConfig.load(DEFAULT_CONFIG_PATH) if DEFAULT_CONFIG_PATH.exists() else MacroConfig()
        self.offset: TimeOffset | None = None
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()

        self._build_ui()
        self._refresh_positions_view()

    # --- UI 구성 ------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm_top = ttk.LabelFrame(self.root, text="1. 클릭 좌표")
        frm_top.pack(fill="x", **pad)

        self.positions_var = tk.StringVar(value="(없음)")
        ttk.Label(frm_top, textvariable=self.positions_var, foreground="#444").pack(anchor="w", padx=8, pady=4)

        btn_row = ttk.Frame(frm_top)
        btn_row.pack(fill="x", padx=6, pady=4)
        ttk.Button(btn_row, text="현재 마우스 위치 추가", command=self.add_current_position).pack(side="left")
        ttk.Button(btn_row, text="3초 후 캡처", command=self.capture_after_delay).pack(side="left", padx=4)
        ttk.Button(btn_row, text="초기화", command=self.clear_positions).pack(side="left")

        ttk.Label(
            frm_top,
            text="팁: 카카오톡 화면에서 [공지 열기 → 특정 공지 → 댓글 입력창] 순으로 좌표를 추가하세요.\n"
                 "    공지 화면을 미리 열어두었다면 [댓글 입력창] 하나면 충분합니다.",
            foreground="#666",
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        frm_text = ttk.LabelFrame(self.root, text="2. 댓글 내용")
        frm_text.pack(fill="both", expand=True, **pad)
        self.text_box = scrolledtext.ScrolledText(frm_text, height=6, wrap="word")
        self.text_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.text_box.insert("1.0", self.cfg.comment_text)

        frm_time = ttk.LabelFrame(self.root, text="3. 목표 시각 (KST)")
        frm_time.pack(fill="x", **pad)
        self.time_var = tk.StringVar(value=self.cfg.target_time_kst or self._default_target_time())
        ttk.Entry(frm_time, textvariable=self.time_var).pack(fill="x", padx=6, pady=4)
        ttk.Label(
            frm_time,
            text="형식: YYYY-MM-DD HH:MM:SS (예: 2026-04-23 20:00:00)",
            foreground="#666",
        ).pack(anchor="w", padx=8, pady=(0, 4))

        frm_opts = ttk.LabelFrame(self.root, text="4. 옵션")
        frm_opts.pack(fill="x", **pad)
        self.enter_var = tk.BooleanVar(value=self.cfg.submit_with_enter)
        ttk.Checkbutton(frm_opts, text="Enter 키로 댓글 전송 (해제 시 Ctrl+Enter)", variable=self.enter_var).pack(anchor="w", padx=8, pady=2)
        row = ttk.Frame(frm_opts)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text="클릭 사이 지연(초):").pack(side="left")
        self.delay_var = tk.DoubleVar(value=self.cfg.step_delay_seconds)
        ttk.Entry(row, textvariable=self.delay_var, width=6).pack(side="left", padx=6)

        frm_actions = ttk.Frame(self.root)
        frm_actions.pack(fill="x", **pad)
        ttk.Button(frm_actions, text="설정 저장", command=self.save_config).pack(side="left")
        ttk.Button(frm_actions, text="설정 불러오기", command=self.load_config).pack(side="left", padx=4)
        ttk.Button(frm_actions, text="NTP 동기화", command=self.sync_ntp).pack(side="left", padx=4)
        ttk.Button(frm_actions, text="리허설(드라이런)", command=lambda: self.start_run(dry_run=True)).pack(side="right", padx=4)
        self.run_button = ttk.Button(frm_actions, text="예약 실행", command=lambda: self.start_run(dry_run=False))
        self.run_button.pack(side="right")

        frm_status = ttk.LabelFrame(self.root, text="상태")
        frm_status.pack(fill="both", expand=True, **pad)
        self.status = scrolledtext.ScrolledText(frm_status, height=8, state="disabled", bg="#111", fg="#eee")
        self.status.pack(fill="both", expand=True, padx=6, pady=6)

        frm_cancel = ttk.Frame(self.root)
        frm_cancel.pack(fill="x", **pad)
        ttk.Button(frm_cancel, text="중단", command=self.cancel).pack(side="right")

    # --- helpers ------------------------------------------------------------
    def _default_target_time(self) -> str:
        # 기본값: 다음 정각
        now = datetime.now(tz=KST).replace(second=0, microsecond=0) + timedelta(minutes=1)
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def log(self, msg: str) -> None:
        def append() -> None:
            self.status.configure(state="normal")
            self.status.insert("end", msg + "\n")
            self.status.see("end")
            self.status.configure(state="disabled")
        self.root.after(0, append)

    def _refresh_positions_view(self) -> None:
        if not self.cfg.click_positions:
            self.positions_var.set("(없음)")
            return
        parts = [f"{i+1}) ({x}, {y})" for i, (x, y) in enumerate(self.cfg.click_positions)]
        self.positions_var.set("   ".join(parts))

    # --- button handlers ----------------------------------------------------
    def add_current_position(self) -> None:
        pos = pyautogui.position()
        self.cfg.click_positions.append((int(pos.x), int(pos.y)))
        self._refresh_positions_view()
        self.log(f"좌표 추가: ({pos.x}, {pos.y})")

    def capture_after_delay(self) -> None:
        def worker() -> None:
            for i in range(3, 0, -1):
                self.log(f"  {i}초 후 캡처...")
                time.sleep(1.0)
            pos = pyautogui.position()
            self.cfg.click_positions.append((int(pos.x), int(pos.y)))
            self.root.after(0, self._refresh_positions_view)
            self.log(f"좌표 추가(지연): ({pos.x}, {pos.y})")
        threading.Thread(target=worker, daemon=True).start()

    def clear_positions(self) -> None:
        self.cfg.click_positions = []
        self._refresh_positions_view()
        self.log("좌표 초기화")

    def _pull_form(self) -> None:
        self.cfg.comment_text = self.text_box.get("1.0", "end-1c")
        self.cfg.target_time_kst = self.time_var.get().strip()
        self.cfg.submit_with_enter = bool(self.enter_var.get())
        try:
            self.cfg.step_delay_seconds = float(self.delay_var.get())
        except Exception:
            self.cfg.step_delay_seconds = 0.25

    def save_config(self) -> None:
        self._pull_form()
        self.cfg.save(DEFAULT_CONFIG_PATH)
        self.log(f"설정 저장 → {DEFAULT_CONFIG_PATH}")

    def load_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        self.cfg = MacroConfig.load(Path(path))
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", self.cfg.comment_text)
        self.time_var.set(self.cfg.target_time_kst)
        self.enter_var.set(self.cfg.submit_with_enter)
        self.delay_var.set(self.cfg.step_delay_seconds)
        self._refresh_positions_view()
        self.log(f"설정 로드 ← {path}")

    def sync_ntp(self) -> None:
        def worker() -> None:
            self.log("NTP 동기화 중...")
            try:
                self.offset = fetch_offset()
                self.log(
                    f"NTP OK: {self.offset.server}  offset={self.offset.offset_seconds*1000:+.1f}ms "
                    f"rtt={self.offset.rtt_seconds*1000:.1f}ms"
                )
            except Exception as exc:  # noqa: BLE001
                self.log(f"NTP 실패: {exc}")
                self.offset = None
        threading.Thread(target=worker, daemon=True).start()

    def cancel(self) -> None:
        self.cancel_flag.set()
        self.log("중단 요청...")

    def start_run(self, *, dry_run: bool) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return

        self._pull_form()

        if not self.cfg.click_positions:
            messagebox.showwarning("설정 부족", "클릭 좌표를 최소 1개 이상 추가하세요.")
            return
        if not self.cfg.comment_text.strip():
            messagebox.showwarning("설정 부족", "댓글 내용을 입력하세요.")
            return
        try:
            target_epoch = parse_kst(self.cfg.target_time_kst)
        except Exception as exc:
            messagebox.showerror("시간 형식 오류", str(exc))
            return

        self.cancel_flag.clear()
        self.worker = threading.Thread(
            target=self._run_worker,
            args=(target_epoch, dry_run),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, target_epoch: float, dry_run: bool) -> None:
        try:
            if self.offset is None:
                self.log("NTP 동기화 선행...")
                self.offset = fetch_offset()
                self.log(
                    f"NTP OK: offset={self.offset.offset_seconds*1000:+.1f}ms "
                    f"(server={self.offset.server})"
                )
            offset = self.offset

            plan = CommentPlan(
                click_positions=self.cfg.click_positions,
                comment_text=self.cfg.comment_text,
                step_delay_seconds=self.cfg.step_delay_seconds,
                submit_with_enter=self.cfg.submit_with_enter,
            )

            remaining = target_epoch - offset.now()
            if remaining < 0:
                self.log(f"목표 시각이 이미 지났습니다 ({remaining:.1f}s)")
                return

            self.log(f"대기 시작: 남은 {remaining:.1f}s")

            last_tick = -1
            focused = False
            while offset.now() < target_epoch - 0.05:
                if self.cancel_flag.is_set():
                    self.log("사용자 중단")
                    return
                rem = target_epoch - offset.now()
                sec = int(rem)
                if sec != last_tick and (sec <= 10 or sec % 10 == 0):
                    self.log(f"  남은 시간 {sec}s")
                    last_tick = sec

                # 5초 이하로 진입하는 순간 한 번만 창 포커싱
                if not focused and rem <= 5.0:
                    focus_kakao_window(self.cfg.window_title_contains)
                    self.log("카카오톡 창 활성화")
                    focused = True

                time.sleep(min(0.2, max(0.01, rem - 0.05)))

            # busy-wait
            while offset.now() < target_epoch:
                if self.cancel_flag.is_set():
                    self.log("사용자 중단")
                    return

            now_kst = datetime.fromtimestamp(offset.now(), tz=KST)
            self.log(f"실행! {now_kst.strftime('%H:%M:%S.%f')[:-3]} KST  (dry_run={dry_run})")
            execute_plan(plan, dry_run=dry_run)
            self.log("완료")
        except Exception as exc:  # noqa: BLE001
            logger.exception("run worker failed")
            self.log(f"에러: {exc}")


def launch() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = tk.Tk()
    MacroApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
