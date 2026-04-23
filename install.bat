@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title 카카오톡 공지 댓글 매크로 - 설치기

set "ROOT=%~dp0"
set "INSTALL_DIR=%ROOT%python"
set "PY_VERSION=3.12.7"
set "PY_ARCH=amd64"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-%PY_ARCH%.exe"
set "PY_INSTALLER=%TEMP%\python-%PY_VERSION%-%PY_ARCH%.exe"

echo ================================================
echo   카카오톡 공지 댓글 매크로 - 설치기
echo ================================================
echo.
echo 설치 위치 : %INSTALL_DIR%
echo Python    : %PY_VERSION% (%PY_ARCH%)
echo.
echo 이 설치기는 관리자 권한이 필요하지 않습니다.
echo 시스템 PATH/레지스트리를 건드리지 않고, 폴더 안에만 설치합니다.
echo.
pause

REM ---------- 1. Python 설치 ----------
if exist "%INSTALL_DIR%\python.exe" (
    echo [스킵] Python이 이미 설치되어 있습니다: %INSTALL_DIR%
    goto install_deps
)

echo.
echo [1/3] Python %PY_VERSION% 다운로드 중...
echo       %PY_URL%

where curl >nul 2>nul
if %errorlevel%==0 (
    curl -L -o "%PY_INSTALLER%" "%PY_URL%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing"
)
if not exist "%PY_INSTALLER%" (
    echo   [실패] Python 설치 파일 다운로드 실패.
    echo          네트워크 또는 회사 프록시/방화벽을 확인하세요.
    echo          수동 다운로드: %PY_URL%
    echo          다운로드한 파일을 %TEMP% 에 두고 다시 실행하세요.
    pause
    exit /b 1
)

echo.
echo [2/3] Python 로컬 설치 중... (수 십 초 소요)
"%PY_INSTALLER%" /quiet ^
  TargetDir="%INSTALL_DIR%" ^
  InstallAllUsers=0 ^
  PrependPath=0 ^
  Shortcuts=0 ^
  Include_doc=0 ^
  Include_test=0 ^
  Include_launcher=0 ^
  Include_tcltk=1 ^
  Include_pip=1 ^
  SimpleInstall=1
set "PY_RC=%errorlevel%"
del "%PY_INSTALLER%" >nul 2>&1
if not "%PY_RC%"=="0" (
    echo   [실패] Python 설치 실패 (코드 %PY_RC%^).
    pause
    exit /b 1
)
if not exist "%INSTALL_DIR%\python.exe" (
    echo   [실패] 설치 후에도 python.exe를 찾을 수 없습니다.
    pause
    exit /b 1
)

:install_deps
REM ---------- 2. 의존성 ----------
echo.
echo [3/3] 의존성 패키지 설치 중...
"%INSTALL_DIR%\python.exe" -m pip install --upgrade pip --disable-pip-version-check --no-warn-script-location
if errorlevel 1 goto deps_fail

"%INSTALL_DIR%\python.exe" -m pip install -r "%ROOT%requirements.txt" --disable-pip-version-check --no-warn-script-location
if errorlevel 1 goto deps_fail

echo.
echo ================================================
echo   설치 완료
echo ================================================
echo.
echo 실행:
echo   - GUI 실행      : run_macro.bat    (더블클릭)
echo   - CLI 실행      : run_macro_cli.bat
echo   - 제거          : uninstall.bat
echo.
pause
exit /b 0

:deps_fail
echo.
echo   [실패] pip 설치 실패. 네트워크 연결을 확인하세요.
pause
exit /b 1
