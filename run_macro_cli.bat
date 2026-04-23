@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "HERE=%~dp0"
set "PYEXE=%HERE%python\python.exe"

if not exist "%PYEXE%" (
    echo Python이 설치되지 않았습니다. install.bat 을 먼저 실행하세요.
    pause
    exit /b 1
)

cd /d "%HERE%"
set "PATH=%HERE%python;%HERE%python\Scripts;%PATH%"

echo ================================================
echo   카카오톡 공지 댓글 매크로 - CLI
echo ================================================
echo.
echo 사용 예:
echo   python run.py now                   서버 시간 확인
echo   python run.py capture -n 3          좌표 캡처 (F9:저장, Esc:취소)
echo   python run.py dry-run --no-wait     리허설
echo   python run.py run                   예약 실행
echo   python run.py gui                   GUI 실행
echo.
echo 이 창을 닫으려면 exit 입력.
echo.

cmd /k
