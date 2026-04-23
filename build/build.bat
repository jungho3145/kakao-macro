@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title KakaoMacro - .exe 빌드

set "HERE=%~dp0"
set "ROOT=%HERE%.."
cd /d "%HERE%"

echo ================================================
echo   KakaoMacro 빌드 (.exe 생성)
echo ================================================
echo.

REM ---------- Python 확인 ----------
set "PYEXE="
if exist "%ROOT%\python\python.exe" (
    set "PYEXE=%ROOT%\python\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel!==0 set "PYEXE=python"
)
if "%PYEXE%"=="" (
    echo [실패] Python을 찾을 수 없습니다.
    echo        먼저 루트의 install.bat 을 실행하거나, Python을 설치하세요.
    pause
    exit /b 1
)
echo Python: %PYEXE%

REM ---------- 의존성 + PyInstaller ----------
echo.
echo [1/3] PyInstaller 및 의존성 설치
"%PYEXE%" -m pip install --upgrade pip --disable-pip-version-check --no-warn-script-location
"%PYEXE%" -m pip install -r "%ROOT%\requirements.txt" --disable-pip-version-check --no-warn-script-location
"%PYEXE%" -m pip install pyinstaller --disable-pip-version-check --no-warn-script-location
if errorlevel 1 (
    echo [실패] 의존성 설치 실패
    pause & exit /b 1
)

REM ---------- PyInstaller ----------
echo.
echo [2/3] PyInstaller로 KakaoMacro.exe 빌드
"%PYEXE%" -m PyInstaller --clean --noconfirm KakaoMacro.spec
if errorlevel 1 (
    echo [실패] PyInstaller 빌드 실패
    pause & exit /b 1
)
if not exist "dist\KakaoMacro.exe" (
    echo [실패] dist\KakaoMacro.exe 가 생성되지 않았습니다.
    pause & exit /b 1
)
echo   [OK] dist\KakaoMacro.exe

REM ---------- Inno Setup (선택) ----------
echo.
echo [3/3] Inno Setup으로 인스톨러 빌드
set "ISCC="
where iscc >nul 2>nul && set "ISCC=iscc"
if "%ISCC%"=="" (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if "%ISCC%"=="" (
    echo   [스킵] Inno Setup이 설치되어 있지 않습니다.
    echo          dist\KakaoMacro.exe 를 그대로 배포하거나,
    echo          Inno Setup 6을 설치한 후 이 스크립트를 다시 실행하세요.
    echo          다운로드: https://jrsoftware.org/isdl.php
    echo.
    echo 빌드 완료: dist\KakaoMacro.exe
    pause
    exit /b 0
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo [실패] Inno Setup 빌드 실패
    pause & exit /b 1
)

echo.
echo ================================================
echo   빌드 완료
echo ================================================
echo.
echo 배포 파일:
echo   - %HERE%dist\KakaoMacro.exe        (단일 실행 파일)
echo   - %HERE%KakaoMacroSetup.exe        (설치 마법사)
echo.
echo 일반 사용자에게는 KakaoMacroSetup.exe 를 전달하세요.
echo.
pause
