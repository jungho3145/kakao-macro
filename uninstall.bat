@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "HERE=%~dp0"

echo ================================================
echo   카카오톡 공지 댓글 매크로 - 제거
echo ================================================
echo.
echo 다음 항목이 삭제됩니다:
echo   - %HERE%python\   (로컬 Python)
echo   - %HERE%__pycache__\ 등 캐시
echo.
echo config.json 은 그대로 남겨 둡니다 (보존).
echo 완전히 지우려면 수동으로 삭제하세요.
echo.

set /p CONFIRM=계속하시겠습니까? (y/N)
if /i not "%CONFIRM%"=="y" (
    echo 취소됨.
    exit /b 0
)

if exist "%HERE%python" (
    echo   python\ 제거 중...
    rmdir /s /q "%HERE%python"
)
if exist "%HERE%__pycache__" rmdir /s /q "%HERE%__pycache__"
if exist "%HERE%src\__pycache__" rmdir /s /q "%HERE%src\__pycache__"

echo.
echo 제거 완료.
pause
