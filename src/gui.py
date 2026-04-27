"""GUI — 일반 사용자가 한 화면에서 모든 설정을 끝내고 실행할 수 있도록 한다.

주된 위치 지정 방식은 "화면 보고 위치 정하기" 모달(스크린샷 클릭)이다. 마우스
좌표를 직접 다루는 옛 방식은 ‘고급 옵션’ 안에 폴백으로 보존했다.
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
from .screen_picker import pick_positions
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
    INITIAL_GEOMETRY = "920x980"
    MIN_WIDTH = 820
    MIN_HEIGHT = 880

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("카카오톡 공지 댓글 매크로")
        root.geometry(self.INITIAL_GEOMETRY)
        root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = root.winfo_width(), root.winfo_height()
        root.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 30)}")

        self.cfg = MacroConfig.load(DEFAULT_CONFIG_PATH) if DEFAULT_CONFIG_PATH.exists() else MacroConfig()
        self.offset: TimeOffset | None = None
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()

        self._advanced_visible = False

        self._build_ui()
        self._refresh_positions_view()
        self._refresh_submit_button_view()

    # ===== UI 구성 ===========================================================
    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # ---- 1. 클릭할 위치 정하기 ------------------------------------------
        frm_pos = ttk.LabelFrame(self.root, text="1. 클릭할 위치 정하기")
        frm_pos.pack(fill="x", **pad)

        ttk.Label(
            frm_pos,
            text="아래 버튼을 누르면 매크로 창이 잠깐 사라지고, 현재 화면이 그대로 캡처됩니다.\n"
                 "그 화면 위에서 ① 댓글 입력창과 ② [등록] 버튼을 차례로 클릭만 하면 됩니다.",
            foreground="#444", justify="left",
        ).pack(anchor="w", padx=10, pady=(6, 4))

        # 큰 기본 버튼
        big_btn = tk.Button(
            frm_pos, text="📷  화면 보고 위치 정하기 (추천)",
            command=self.open_screen_picker,
            font=("Malgun Gothic", 12, "bold"),
            bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white",
            cursor="hand2", relief="flat", padx=18, pady=10,
        )
        big_btn.pack(anchor="w", padx=10, pady=(2, 8))

        ttk.Label(
            frm_pos, text="위 버튼을 누르기 전에 카카오톡에서 댓글을 달 공지 화면을 미리 띄워 두세요.",
            foreground="#777",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        ttk.Separator(frm_pos, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # 저장된 위치 표시
        status_box = ttk.Frame(frm_pos)
        status_box.pack(fill="x", padx=10, pady=(4, 8))

        self.input_pos_var = tk.StringVar()
        self.submit_pos_var = tk.StringVar()
        ttk.Label(status_box, textvariable=self.input_pos_var,
                  foreground="#0066aa", font=("Malgun Gothic", 10, "bold")).pack(anchor="w", pady=2)
        ttk.Label(status_box, textvariable=self.submit_pos_var,
                  foreground="#0066aa", font=("Malgun Gothic", 10, "bold")).pack(anchor="w", pady=2)

        # 고급 토글 + 영역
        self.advanced_btn = ttk.Button(
            frm_pos, text="▶ 고급 옵션 (마우스 위치로 직접 저장)",
            command=self.toggle_advanced,
        )
        self.advanced_btn.pack(anchor="w", padx=10, pady=(4, 6))

        self.frm_advanced = ttk.Frame(frm_pos)
        self._build_advanced_ui(self.frm_advanced)
        # 고급 영역은 기본 숨김

        # ---- 2. 댓글 내용 ---------------------------------------------------
        frm_text = ttk.LabelFrame(self.root, text="2. 등록할 댓글 내용")
        frm_text.pack(fill="both", expand=True, **pad)
        self.text_box = scrolledtext.ScrolledText(
            frm_text, height=5, wrap="word", font=("Malgun Gothic", 11),
        )
        self.text_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.text_box.insert("1.0", self.cfg.comment_text)

        # ---- 3. 등록할 시각 -------------------------------------------------
        frm_time = ttk.LabelFrame(self.root, text="3. 등록할 시각 (한국 시간)")
        frm_time.pack(fill="x", **pad)
        self.time_var = tk.StringVar(value=self.cfg.target_time_kst or self._default_target_time())
        ttk.Entry(frm_time, textvariable=self.time_var, font=("Consolas", 11)).pack(fill="x", padx=6, pady=4)
        ttk.Label(
            frm_time,
            text="형식: 연-월-일 시:분:초    (예: 2026-04-23 20:00:00)\n"
                 "프로그램이 인터넷의 한국 표준 시계와 동기화하여 정확히 이 시각에 댓글을 등록합니다.",
            foreground="#666", justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 4))

        # ---- 4. 세부 설정 ---------------------------------------------------
        frm_opts = ttk.LabelFrame(self.root, text="4. 세부 설정 (보통은 그대로 두세요)")
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
            frm_status, height=8, state="disabled",
            bg="#0e0e0e", fg="#e8e8e8", font=("Consolas", 10),
        )
        self.status.pack(fill="both", expand=True, padx=6, pady=6)

        frm_cancel = ttk.Frame(self.root)
        frm_cancel.pack(fill="x", **pad)
        ttk.Button(frm_cancel, text="실행 중단", command=self.cancel).pack(side="right")

    def _build_advanced_ui(self, parent: ttk.Frame) -> None:
        """고급 옵션 — 기존 마우스 위치 캡처 방식을 보존."""
        ttk.Label(
            parent,
            text="화면 캡처 방식이 잘 안 될 때 사용하세요. 마우스를 정확한 자리에 둔 뒤\n"
                 "해당 버튼을 누르거나 ‘3초 뒤 저장’을 누르고 마우스를 그 자리에 두세요.",
            foreground="#666", justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 4))

        # 클릭할 위치들
        sub1 = ttk.LabelFrame(parent, text="댓글 입력창까지의 클릭 (여러 단계 가능)")
        sub1.pack(fill="x", padx=6, pady=4)

        self.positions_list_var = tk.StringVar()
        ttk.Label(sub1, textvariable=self.positions_list_var,
                  foreground="#0066aa", wraplength=820, justify="left").pack(anchor="w", padx=8, pady=4)

        row1 = ttk.Frame(sub1)
        row1.pack(fill="x", padx=6, pady=4)
        ttk.Button(row1, text="현재 마우스 위치 추가", command=self.add_current_position).pack(side="left")
        ttk.Button(row1, text="3초 뒤 마우스 위치 추가", command=self.capture_after_delay).pack(side="left", padx=6)
        ttk.Button(row1, text="모두 지우기", command=self.clear_positions).pack(side="left")

        # 등록 버튼 위치
        sub2 = ttk.LabelFrame(parent, text="등록 버튼 위치")
        sub2.pack(fill="x", padx=6, pady=4)

        row2 = ttk.Frame(sub2)
        row2.pack(fill="x", padx=6, pady=4)
        ttk.Button(row2, text="현재 마우스 위치를 등록 버튼으로 저장",
                   command=self.set_submit_button_now).pack(side="left")
        ttk.Button(row2, text="3초 뒤 등록 버튼 위치 저장",
                   command=self.set_submit_button_delayed).pack(side="left", padx=6)
        ttk.Button(row2, text="등록 버튼 지우기",
                   command=self.clear_submit_button).pack(side="left")

    def toggle_advanced(self) -> None:
        if self._advanced_visible:
            self.frm_advanced.pack_forget()
            self.advanced_btn.config(text="▶ 고급 옵션 (마우스 위치로 직접 저장)")
            self._advanced_visible = False
        else:
            self.frm_advanced.pack(fill="x", padx=10, pady=(4, 8))
            self.advanced_btn.config(text="▼ 고급 옵션 (마우스 위치로 직접 저장)")
            self._advanced_visible = True

    # ===== 헬퍼 ==============================================================
    def _default_target_time(self) -> str:
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
        # 기본 표시: 마지막 위치를 ‘댓글 입력창’ 위치로 본다
        if not self.cfg.click_positions:
            self.input_pos_var.set("①  댓글 입력창 위치:  (아직 정해지지 않았습니다)")
        else:
            x, y = self.cfg.click_positions[-1]
            extra = ""
            if len(self.cfg.click_positions) > 1:
                extra = f"  + 그 전에 {len(self.cfg.click_positions) - 1}단계의 추가 클릭"
            self.input_pos_var.set(f"①  댓글 입력창 위치:  ({x}, {y}){extra}")
        # 고급 영역의 상세 목록도 갱신
        if hasattr(self, "positions_list_var"):
            if not self.cfg.click_positions:
                self.positions_list_var.set("(저장된 클릭이 없습니다)")
            else:
                parts = [f"{i+1}) ({x}, {y})" for i, (x, y) in enumerate(self.cfg.click_positions)]
                self.positions_list_var.set("   ".join(parts))

    def _refresh_submit_button_view(self) -> None:
        if self.cfg.submit_button_position is None:
            self.submit_pos_var.set("②  [등록] 버튼 위치:  (아직 정해지지 않았습니다)")
        else:
            x, y = self.cfg.submit_button_position
            self.submit_pos_var.set(f"②  [등록] 버튼 위치:  ({x}, {y})")

    # ===== 화면 보고 위치 정하기 =============================================
    def open_screen_picker(self) -> None:
        self.log("화면을 캡처합니다... 매크로 창이 잠시 사라집니다.")
        try:
            result = pick_positions(self.root)
        except Exception as exc:  # noqa: BLE001
            self.log(f"화면 캡처에 실패했습니다: {exc}")
            messagebox.showerror(
                "화면 캡처 실패",
                f"화면 캡처에 실패했습니다.\n\n{exc}\n\n"
                "‘고급 옵션’의 마우스 위치 저장을 사용해 보세요.",
            )
            return

        if not result.confirmed:
            self.log("화면 캡처가 취소되었습니다.")
            return

        # 단순 모드: 입력창 1개 + 등록 버튼 1개로 덮어쓰기
        if result.input_position is not None:
            self.cfg.click_positions = [result.input_position]
        if result.submit_position is not None:
            self.cfg.submit_button_position = result.submit_position
        self._refresh_positions_view()
        self._refresh_submit_button_view()
        self.log(
            f"위치 저장 완료 — 입력창 {result.input_position}, "
            f"등록 버튼 {result.submit_position}"
        )

    # ===== 고급(마우스) — 클릭 위치 ==========================================
    def add_current_position(self) -> None:
        pos = pyautogui.position()
        self.cfg.click_positions.append((int(pos.x), int(pos.y)))
        self._refresh_positions_view()
        self.log(f"클릭 위치 추가: ({pos.x}, {pos.y})")

    def capture_after_delay(self) -> None:
        def worker() -> None:
            for i in range(3, 0, -1):
                self.log(f"  {i}초 뒤 마우스 위치를 저장합니다...")
                time.sleep(1.0)
            pos = pyautogui.position()
            self.cfg.click_positions.append((int(pos.x), int(pos.y)))
            self.root.after(0, self._refresh_positions_view)
            self.log(f"클릭 위치 추가(3초 뒤): ({pos.x}, {pos.y})")
        threading.Thread(target=worker, daemon=True).start()

    def clear_positions(self) -> None:
        self.cfg.click_positions = []
        self._refresh_positions_view()
        self.log("저장된 클릭 위치를 모두 지웠습니다.")

    # ===== 고급(마우스) — 등록 버튼 ==========================================
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
                self.log(f"서버 시간 동기화 완료 (내 컴퓨터 시계와의 차이: {gap_ms:+.1f}ms)")
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
                "위치를 먼저 정해 주세요",
                "‘1. 클릭할 위치 정하기’에서 ‘화면 보고 위치 정하기’ 버튼을 눌러 위치를 저장해 주세요.",
            )
            return
        if not self.cfg.comment_text.strip():
            messagebox.showwarning("댓글 내용 없음", "‘2. 등록할 댓글 내용’을 입력해 주세요.")
            return
        if self.cfg.submit_button_position is None:
            ok = messagebox.askyesno(
                "등록 버튼 위치가 없습니다",
                "카카오톡 공지 댓글은 Enter 키로 등록되지 않고 ‘등록’ 버튼을 클릭해야 등록됩니다.\n\n"
                "‘등록 버튼 위치’가 정해지지 않은 상태입니다. 그래도 진행하시겠습니까?\n"
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
                self.log(f"서버 시간 동기화 완료 (차이: {self.offset.offset_seconds*1000:+.1f}ms)")
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

                if not focused and rem <= 5.0:
                    if focus_kakao_window(self.cfg.window_title_contains):
                        self.log("카카오톡 창을 앞으로 가져왔습니다.")
                    focused = True

                time.sleep(min(0.2, max(0.01, rem - 0.05)))

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
    try:
        dpi = root.winfo_fpixels("1i")
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:  # noqa: BLE001
        pass
    MacroApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
