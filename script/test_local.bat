@echo off
rem ====== 本地真机测试（MuMu 模拟器）======
rem CI 不跑这里。模拟器未运行会自动拉起（约 1-3 分钟）；
rem 设 DELI_LOCAL_NO_START=1 可禁止自动启动。
rem 用法：双击运行，或命令行传 pytest 参数：test_local.bat -k launch
setlocal
set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] venv not found: %PYTHON%
    echo Run first:  python -m venv .venv  ^&^&  .venv\Scripts\pip install -e ".[dev]"
    pause
    exit /b 1
)

pushd "%ROOT%"
"%PYTHON%" -m pytest tests_local -v --tb=short %*
set "CODE=%ERRORLEVEL%"
popd

echo.
if "%CODE%"=="0" (echo [OK] all local device tests passed.) else (echo [FAIL] exit code %CODE%)
pause
endlocal & exit /b %CODE%
