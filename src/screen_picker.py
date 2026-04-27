"""스크린샷 위에서 클릭 위치를 직접 지정하는 모달 창.

기존의 "마우스를 위치에 두고 3초 기다리기" 방식은 일반 사용자에게 어색하다.
대신 화면을 통째로 캡처해 새 창에 띄우고, 사용자가 그 위에서 ① 댓글 입력창과
② [등록] 버튼을 차례로 클릭하면 그대로 좌표가 저장된다. 윈도우의 화면 캡처
도구와 동일한 UX다.
"""
from __future__ import annotations

import logging
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

import pyautogui
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreenPickResult:
    """`pick_positions`의 결과.

    confirmed=False면 사용자가 취소한 것.
    """

    input_position: tuple[int, int] | None
    submit_position: tuple[int, int] | None
    confirmed: bool


def pick_positions(parent: tk.Misc) -> ScreenPickResult:
    """모달로 두 위치(댓글 입력창, 등록 버튼)를 받아 반환한다."""
    img = _capture_full_screen(parent)
    if img is None:
        return ScreenPickResult(None, None, confirmed=False)

    screen_w = parent.winfo_screenwidth()
    screen_h = parent.winfo_screenheight()
    img_w, img_h = img.size

    # 모니터의 약 85% 안에 들어가도록 표시 비율 결정.
    max_w = int(screen_w * 0.88)
    max_h = int(screen_h * 0.82)
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    disp_w = max(1, int(img_w * scale))
    disp_h = max(1, int(img_h * scale))
    display_img = img.resize((disp_w, disp_h), Image.LANCZOS) if scale < 1.0 else img

    win = tk.Toplevel(parent)
    win.title("화면에서 클릭할 위치를 정해주세요")
    win.transient(parent)
    win.grab_set()
    win.configure(bg="#111")

    photo = ImageTk.PhotoImage(display_img)

    state: dict[str, object] = {
        "step": 0,        # 0=input, 1=submit, 2=done
        "input": None,
        "submit": None,
        "confirmed": False,
    }

    inst_var = tk.StringVar()

    # 상단 안내 바
    top = tk.Frame(win, bg="#1f2937")
    top.pack(fill="x")
    tk.Label(
        top, textvariable=inst_var,
        bg="#1f2937", fg="#f9fafb",
        font=("Malgun Gothic", 14, "bold"),
        pady=10,
    ).pack(anchor="w", padx=14)

    # 캔버스 (스크린샷 + 클릭 마커)
    canvas = tk.Canvas(
        win, width=disp_w, height=disp_h,
        highlightthickness=0, cursor="crosshair", bg="#000",
    )
    canvas.pack()
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.image = photo  # keep reference, GC 방지

    # 하단 버튼 바
    bottom = tk.Frame(win, bg="#111")
    bottom.pack(fill="x", padx=12, pady=10)

    confirm_btn = ttk.Button(bottom, text="확인", state="disabled")
    redo_btn = ttk.Button(bottom, text="다시 하기")
    cancel_btn = ttk.Button(bottom, text="취소")

    redo_btn.pack(side="left")
    confirm_btn.pack(side="right")
    cancel_btn.pack(side="right", padx=6)

    def update_inst() -> None:
        step = state["step"]
        if step == 0:
            inst_var.set("①  댓글 입력창 위치를 클릭하세요")
        elif step == 1:
            inst_var.set("②  이번엔 [등록] 버튼 위치를 클릭하세요")
        else:
            inst_var.set("완료! 아래 [확인]을 누르거나 [다시 하기]를 누르세요.")

    def reset() -> None:
        state["step"] = 0
        state["input"] = None
        state["submit"] = None
        canvas.delete("marker")
        confirm_btn.config(state="disabled")
        update_inst()

    def on_click(event: tk.Event) -> None:  # type: ignore[type-arg]
        step = state["step"]
        if step >= 2:
            return

        # 표시 좌표 → 실제 화면 좌표 (스케일 역변환)
        ox = int(event.x / scale)
        oy = int(event.y / scale)

        if step == 0:
            state["input"] = (ox, oy)
            color, label = "#ef4444", "①"
        else:
            state["submit"] = (ox, oy)
            color, label = "#10b981", "②"

        r = 16
        canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            outline=color, width=3, tags="marker",
        )
        canvas.create_oval(
            event.x - 3, event.y - 3, event.x + 3, event.y + 3,
            fill=color, outline=color, tags="marker",
        )
        canvas.create_text(
            event.x + 22, event.y - 18, text=label,
            fill=color, font=("Arial", 16, "bold"), tags="marker",
        )

        state["step"] = step + 1
        update_inst()
        if state["step"] >= 2:
            confirm_btn.config(state="normal")

    def confirm() -> None:
        if state["step"] < 2:
            return
        state["confirmed"] = True
        win.destroy()

    def cancel() -> None:
        state["confirmed"] = False
        win.destroy()

    confirm_btn.config(command=confirm)
    redo_btn.config(command=reset)
    cancel_btn.config(command=cancel)
    canvas.bind("<Button-1>", on_click)
    win.bind("<Escape>", lambda _e: cancel())

    update_inst()
    win.update_idletasks()
    # 화면 가운데로 이동
    ww, wh = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{(screen_w - ww) // 2}+{max(20, (screen_h - wh) // 2 - 30)}")

    win.wait_window()

    if not state["confirmed"]:
        return ScreenPickResult(None, None, confirmed=False)
    return ScreenPickResult(
        input_position=state["input"],     # type: ignore[arg-type]
        submit_position=state["submit"],   # type: ignore[arg-type]
        confirmed=True,
    )


def _capture_full_screen(parent: tk.Misc) -> Image.Image | None:
    """parent 창을 잠시 숨기고 전체 화면 스크린샷을 찍는다.

    화면이 실제로 다시 그려질 시간을 위해 `time.sleep`로 짧게 대기. 실패해도
    None을 반환해 호출자가 우아하게 폴백할 수 있도록 한다.
    """
    try:
        parent.withdraw()
        parent.update()
        time.sleep(0.6)  # OS가 창을 실제로 화면에서 치울 시간
        img = pyautogui.screenshot()
        return img
    except Exception as exc:  # noqa: BLE001
        logger.exception("screenshot failed: %s", exc)
        return None
    finally:
        try:
            parent.deiconify()
            parent.update()
        except Exception:  # noqa: BLE001
            pass
