"""GUI — 일반 사용자가 한 화면에서 모든 설정을 끝내고 실행할 수 있도록 한다.

전문 용어를 피하고 한국어 설명 위주로 라벨을 구성했다. 시간 동기화/스케줄링 같은
내부 동작은 백그라운드 스레드에서 실행하고, 진행 상황을 하단 로그창에 표시한다.
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
from .scheduler import parse_kst
from .time_sync import TimeOffset, fetch_offset

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

DEFAULT_CONFIG_PATH = Path("config.json")


def _enable_windows_dpi_awareness() -> None:
    """Windows 디스플레이 배율(125%/150%)에서 글자가 흐려지지 않게 한다."""
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
    except Exception:  # noqa: BLE001
        pass


class MacroApp:
    INITIAL_GEOMETRY = "960x1100"
    MIN_WIDTH = 820
    MIN_HEIGHT = 940

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("카카오톡 공지 댓글 매크로")
        root.geometry(self.INITIAL_GEOMETRY)
        root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        # 화면 가운데 정렬
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = root.winfo_width(), root.winfo_height()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 30)
        root.geometry(f"+{x}+{y}")

        self.cfg = MacroConfig.load(DEFAULT_CONFIG_PATH) if DEFAULT_CONFIG_PATH.exists() else MacroConfig()
        self.offset: TimeOffset | None = None
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()

        self._build_ui()
        self._refresh_positions_view()
        self._refresh_submit_button_view()

    # ===== UI 구성 ===========================================================
    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # ---- 1. 댓글 입력창까지 클릭할 위치 -------------------------------
        frm_top = ttk.LabelFrame(self.root, text="1. 댓글 입력창까지 클릭할 위치")
        frm_top.pack(fill="x", **pad)

        ttk.Label(
            frm_top,
            text="카카오톡 화면에서 댓글을 다는 데까지 거쳐야 하는 클릭들을 순서대로 저장합니다.\n"
                 "예: ① 공지 아이콘 → ② 댓글 달 공지 → ③ 댓글 입력창 클릭\n"
                 "이미 공지를 열어 두셨다면 ‘댓글 입력창’ 한 곳만 저장하셔도 됩니다.",
            foreground="#444", justify="left",
        ).pack(anchor="w", padx=8, pady=(4, 6))

        self.positions_var = tk.StringVar(value="(아직 저장된 위치가 없습니다)")
        ttk.Label(frm_top, textvariable=self.positions_var, foreground="#0066aa", wraplength=900,
                  justify="left").pack(anchor="w", padx=8, pady=2)

        btn_row = ttk.Frame(frm_top)
        btn_row.pack(fill="x", padx=6, pady=6)
        ttk.Button(btn_row, text="현재 마우스 위치 저장", command=self.add_current_position).pack(side="left")
        ttk.Button(btn_row, text="3초 뒤 마우스 위치 저장", command=self.capture_after_delay).pack(side="left", padx=6)
        ttk.Button(btn_row, text="모두 지우기", command=self.clear_positions).pack(side="left")

        # ---- 2. 댓글 내용 ---------------------------------------------------
        frm_text = ttk.LabelFrame(self.root, text="2. 등록할 댓글 내용")
        frm_text.pack(fill="both", expand=True, **pad)
        self.text_box = scrolledtext.ScrolledText(frm_text, height=6, wrap="word",
                                                  font=("Malgun Gothic", 11))
        self.text_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.text_box.insert("1.0", self.cfg.comment_text)

        # ---- 3. 등록 버튼 위치 ----------------------------------------------
        frm_submit = ttk.LabelFrame(self.root, text="3. ‘등록’ 버튼 위치 (필수)")
        frm_submit.pack(fill="x", **pad)

        ttk.Label(
            frm_submit,
            text="카카오톡 공지 댓글은 Enter 키로는 등록되지 않고 ‘등록’ 버튼을 눌러야 등록됩니다.\n"
                 "댓글 내용을 입력했을 때 나타나는 [등록] 버튼 위에 마우스를 올린 뒤 아래 버튼을 누르세요.",
            foreground="#444", justify="left",
        ).pack(anchor="w", padx=8, pady=(4, 6))

        self.submit_pos_var = tk.StringVar()
        ttk.Label(frm_submit, textvariable=self.submit_pos_var,
                  foreground="#0066aa").pack(anchor="w", padx=8, pady=2)

        srow = ttk.Frame(frm_submit)
        srow.pack(fill="x", padx=6, pady=6)
        ttk.Button(srow, text="현재 마우스 위치를 ‘등록 버튼’으로 저장",
                   command=self.set_submit_button_now).pack(side="left")
        ttk.Button(srow, text="3초 뒤 ‘등록 버튼’ 위치 저장",
                   command=self.set_submit_button_delayed).pack(side="left", padx=6)
        ttk.Button(srow, text="등록 버튼 지우기",
                   command=self.clear_submit_button).pack(side="left")

        # ---- 4. 등록할 시각 -------------------------------------------------
        frm_time = ttk.LabelFrame(self.root, text="4. 등록할 시각 (한국 시간)")
        frm_time.pack(fill="x", **pad)
        self.time_var = tk.StringVar(value=self.cfg.target_time_kst or self._default_target_time())
        ttk.Entry(frm_time, textvariable=self.time_var, font=("Consolas", 11)).pack(fill="x", padx=6, pady=4)
        ttk.Label(
            frm_time,
            text="형식: 연-월-일 시:분:초    (예: 2026-04-23 20:00:00)\n"
                 "프로그램이 인터넷의 한국 표준 시계와 동기화하여 정확히 이 시각에 댓글을 등록합니다.",
            foreground="#666", justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 4))

        # ---- 5. 세부 설정 ---------------------------------------------------
        frm_opts = ttk.LabelFrame(self.root, text="5. 세부 설정 (보통은 그대로 두세요)")
        frm_opts.pack(fill="x", **pad)

        row = ttk.Frame(frm_opts)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="클릭 사이 잠시 기다리기(초):").pack(side="left")
        self.delay_var = tk.DoubleVar(value=self.cfg.step_delay_seconds)
        ttk.Entry(row, textvariable=self.delay_var, width=6).pack(side="left", padx=6)
        ttk.Label(row, text="(화면이 다음 단계로 바뀌는 시간을 기다립니다)",
                  foreground="#888").pack(side="left")

        self.enter_var = tk.BooleanVar(value=self.cfg.submit_with_enter)
        ttk.Checkbutton(
            frm_opts,
            text="‘등록 버튼 위치’가 비어 있을 때만 Enter 키로 보내기 (체크 해제 시 Ctrl+Enter)",
            variable=self.enter_var,
        ).pack(anchor="w", padx=8, pady=2)

        # ---- 작업 버튼 ------------------------------------------------------
        frm_actions = ttk.Frame(self.root)
        frm_actions.pack(fill="x", **pad)
        ttk.Button(frm_actions, text="설정 저장하기", command=self.save_config).pack(side="left")
        ttk.Button(frm_actions, text="저장된 설정 불러오기", command=self.load_config).pack(side="left", padx=4)
        ttk.Button(frm_actions, text="서버 시간 가져오기", command=self.sync_ntp).pack(side="left", padx=4)
        ttk.Button(frm_actions, text="예행 연습 (실제 등록 안 함)",
                   command=lambda: self.start_run(dry_run=True)).pack(side="right", padx=4)
        self.run_button = ttk.Button(frm_actions, text="시작",
                                     command=lambda: self.start_run(dry_run=False))
        self.run_button.pack(side="right")

        # ---- 진행 상태 ------------------------------------------------------
        frm_status = ttk.LabelFrame(self.root, text="진행 상태")
        frm_status.pack(fill="both", expand=True, **pad)
        self.status = scrolledtext.ScrolledText(
            frm_status, height=10, state="disabled",
            bg="#0e0e0e", fg="#e8e8e8", font=("Consolas", 10),
        )
        self.status.pack(fill="both", expand=True, padx=6, pady=6)

        frm_cancel = ttk.Frame(self.root)
        frm_cancel.pack(fill="x", **pad)
        ttk.Button(frm_cancel, text="실행 중단", command=self.cancel).pack(side="right")

    # ===== 헬퍼 ==============================================================
    def _default_target_time(self) -> str:
        """기본값: 1분 뒤 정각."""
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
            self.positions_var.set("(아직 저장된 위치가 없습니다)")
            return
        parts = [f"{i+1}번째: ({x}, {y})" for i, (x, y) in enumerate(self.cfg.click_positions)]
        self.positions_var.set("   ".join(parts))

    def _refresh_submit_button_view(self) -> None:
        if self.cfg.submit_button_position is None:
            self.submit_pos_var.set("(등록 버튼 위치가 저장되지 않았습니다)")
        else:
            x, y = self.cfg.submit_button_position
            self.submit_pos_var.set(f"등록 버튼 위치: ({x}, {y})")

    # ===== 1. 클릭 위치 ======================================================
    def add_current_position(self) -> None:
        pos = pyautogui.position()
        self.cfg.click_positions.append((int(pos.x), int(pos.y)))
        self._refresh_positions_view()
        self.log(f"클릭 위치 저장: ({pos.x}, {pos.y})")

    def capture_after_delay(self) -> None:
        def worker() -> None:
            for i in range(3, 0, -1):
                self.log(f"  {i}초 뒤 마우스 위치를 저장합니다...")
                time.sleep(1.0)
            pos = pyautogui.position()
            self.cfg.click_positions.append((int(pos.x), int(pos.y)))
            self.root.after(0, self._refresh_positions_view)
            self.log(f"클릭 위치 저장(3초 뒤): ({pos.x}, {pos.y})")
        threading.Thread(target=worker, daemon=True).start()

    def clear_positions(self) -> None:
        self.cfg.click_positions = []
        self._refresh_positions_view()
        self.log("저장된 클릭 위치를 모두 지웠습니다.")

    # ===== 3. 등록 버튼 ======================================================
    def set_submit_button_now(self) -> None:
        pos = pyautogui.position()
        self.cfg.submit_button_position = (int(pos.x), int(pos.y))
        self._refresh_submit_button_view()
        self.log(f"등록 버튼 위치 저장: ({pos.x}, {pos.y})")

    def set_submit_button_delayed(self) -> None:
        def worker() -> None:
            for i in range(3, 0, -1):
                self.log(f"  {i}초 뒤 등록 버튼 위치를 저장합니다...")
                time.sleep(1.0)
            pos = pyautogui.position()
            self.cfg.submit_button_position = (int(pos.x), int(pos.y))
            self.root.after(0, self._refresh_submit_button_view)
            self.log(f"등록 버튼 위치 저장(3초 뒤): ({pos.x}, {pos.y})")
        threading.Thread(target=worker, daemon=True).start()

    def clear_submit_button(self) -> None:
        self.cfg.submit_button_position = None
        self._refresh_submit_button_view()
        self.log("등록 버튼 위치를 지웠습니다.")

    # ===== 폼 ↔ 설정 동기화 =================================================
    def _pull_form(self) -> None:
        self.cfg.comment_text = self.text_box.get("1.0", "end-1c")
        self.cfg.target_time_kst = self.time_var.get().strip()
        self.cfg.submit_with_enter = bool(self.enter_var.get())
        try:
            self.cfg.step_delay_seconds = float(self.delay_var.get())
        except Exception:  # noqa: BLE001
            self.cfg.step_delay_seconds = 0.25

    def save_config(self) -> None:
        self._pull_form()
        self.cfg.save(DEFAULT_CONFIG_PATH)
        self.log(f"설정을 저장했습니다 → {DEFAULT_CONFIG_PATH}")

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
        self._refresh_submit_button_view()
        self.log(f"설정을 불러왔습니다 ← {path}")

    # ===== 시간 동기화 =======================================================
    def sync_ntp(self) -> None:
        def worker() -> None:
            self.log("서버 시간을 가져오는 중입니다...")
            try:
                self.offset = fetch_offset()
                gap_ms = self.offset.offset_seconds * 1000.0
                self.log(
                    f"서버 시간 동기화 완료 (내 컴퓨터 시계와의 차이: {gap_ms:+.1f}ms)"
                )
            except Exception as exc:  # noqa: BLE001
                self.log(f"서버 시간 가져오기에 실패했습니다: {exc}")
                self.offset = None
        threading.Thread(target=worker, daemon=True).start()

    def cancel(self) -> None:
        self.cancel_flag.set()
        self.log("중단을 요청했습니다.")

    # ===== 실행 ==============================================================
    def start_run(self, *, dry_run: bool) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("이미 진행 중", "이미 실행 중입니다.")
            return

        self._pull_form()

        if not self.cfg.click_positions:
            messagebox.showwarning(
                "위치를 먼저 저장해 주세요",
                "‘1. 댓글 입력창까지 클릭할 위치’에서 최소 한 곳 이상의 위치를 저장해야 합니다.",
            )
            return
        if not self.cfg.comment_text.strip():
            messagebox.showwarning("댓글 내용 없음", "‘2. 등록할 댓글 내용’을 입력해 주세요.")
            return
        if self.cfg.submit_button_position is None:
            ok = messagebox.askyesno(
                "등록 버튼 위치가 없습니다",
                "카카오톡 공지 댓글은 Enter 키로 등록되지 않고 ‘등록’ 버튼을 클릭해야 등록됩니다.\n\n"
                "등록 버튼 위치를 저장하지 않은 상태입니다. 그래도 진행하시겠습니까?\n"
                "(이 경우 Enter 키로 시도되며 댓글이 등록되지 않을 수 있습니다.)",
            )
            if not ok:
                return

        try:
            target_epoch = parse_kst(self.cfg.target_time_kst)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("시간 형식이 잘못되었습니다", str(exc))
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
                self.log("먼저 서버 시간을 동기화합니다...")
                self.offset = fetch_offset()
                self.log(
                    f"서버 시간 동기화 완료 "
                    f"(차이: {self.offset.offset_seconds*1000:+.1f}ms)"
                )
            offset = self.offset

            plan = CommentPlan(
                click_positions=self.cfg.click_positions,
                comment_text=self.cfg.comment_text,
                step_delay_seconds=self.cfg.step_delay_seconds,
                submit_button_position=self.cfg.submit_button_position,
                submit_with_enter=self.cfg.submit_with_enter,
            )

            remaining = target_epoch - offset.now()
            if remaining < 0:
                self.log(f"입력하신 시각이 이미 지났습니다 ({remaining:.1f}초 전)")
                return

            mode_str = "예행 연습" if dry_run else "실제 등록"
            self.log(f"[{mode_str}] 대기 시작 — 남은 시간 {remaining:.1f}초")

            last_tick = -1
            focused = False
            while offset.now() < target_epoch - 0.05:
                if self.cancel_flag.is_set():
                    self.log("사용자가 중단했습니다.")
                    return
                rem = target_epoch - offset.now()
                sec = int(rem)
                if sec != last_tick and (sec <= 10 or sec % 30 == 0):
                    self.log(f"  남은 시간 {sec}초")
                    last_tick = sec

                # 5초 이하 진입 시 한 번만 카카오톡 창을 앞으로 가져옴
                if not focused and rem <= 5.0:
                    if focus_kakao_window(self.cfg.window_title_contains):
                        self.log("카카오톡 창을 앞으로 가져왔습니다.")
                    focused = True

                time.sleep(min(0.2, max(0.01, rem - 0.05)))

            # 마지막 50ms는 정밀 대기
            while offset.now() < target_epoch:
                if self.cancel_flag.is_set():
                    self.log("사용자가 중단했습니다.")
                    return

            now_kst = datetime.fromtimestamp(offset.now(), tz=KST)
            self.log(f"실행 시각: {now_kst.strftime('%H:%M:%S.%f')[:-3]} ({mode_str})")
            execute_plan(plan, dry_run=dry_run)
            self.log("완료되었습니다.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("run worker failed")
            self.log(f"오류가 발생했습니다: {exc}")


def launch() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    # 시스템 DPI에 맞춰 Tk 위젯 크기 보정
    try:
        dpi = root.winfo_fpixels("1i")  # 1인치당 픽셀
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:  # noqa: BLE001
        pass
    MacroApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
