@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "HERE=%~dp0"
set "PYEXE=%HERE%python\python.exe"

if not exist "%PYEXE%" (
    echo Python이 설치되지 않았습니다.
    echo install.bat 을 먼저 실행하세요.
    pause
    exit /b 1
)

cd /d "%HERE%"
"%PYEXE%" run.py gui
set "RC=%errorlevel%"
if not "%RC%"=="0" (
    echo.
    echo 프로그램이 비정상 종료되었습니다 (코드 %RC%^).
    pause
)
exit /b %RC%
