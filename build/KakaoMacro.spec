# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 단일 windowed .exe 생성.

빌드 커맨드:
    cd build
    pyinstaller --clean --noconfirm KakaoMacro.spec

산출물:
    build/dist/KakaoMacro.exe
"""
from pathlib import Path

# spec 파일이 build/ 에 있으므로 프로젝트 루트는 부모 디렉터리
PROJECT_ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]  # noqa: F821
ENTRY_SCRIPT = str(PROJECT_ROOT / "app.py")

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "config.example.json"), "."),
        (str(PROJECT_ROOT / "README.md"), "."),
    ],
    hiddenimports=[
        # pyautogui, pyperclip, pygetwindow, ntplib 는 자동 감지되지만
        # Windows 한정 서브모듈을 명시
        "pyperclip",
        "pygetwindow",
        "ntplib",
        "pyautogui",
        "keyboard",
        "PIL.Image",
        "PIL.ImageGrab",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="KakaoMacro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 콘솔 창 숨김 (windowed)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "build" / "icon.ico") if (PROJECT_ROOT / "build" / "icon.ico").exists() else None,
    version=str(PROJECT_ROOT / "build" / "version_info.txt") if (PROJECT_ROOT / "build" / "version_info.txt").exists() else None,
)
