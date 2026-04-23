"""GUI 전용 엔트리 포인트.

PyInstaller가 이 파일을 기준으로 단일 실행 파일을 만든다. CLI는 `run.py`를
그대로 유지하고, 일반 사용자용 .exe는 곧바로 GUI로 진입시키기 위해 별도 진입점을
분리했다.
"""
from __future__ import annotations

import logging
import sys
import traceback
from tkinter import messagebox


def main() -> int:
    try:
        from src.gui import launch
        launch()
        return 0
    except Exception:  # noqa: BLE001
        # .exe로 빌드된 경우 콘솔이 없으므로 사용자에게 메시지박스로 알림
        logging.exception("unhandled error")
        try:
            messagebox.showerror(
                "실행 오류",
                "프로그램이 비정상 종료되었습니다.\n\n" + traceback.format_exc(),
            )
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
