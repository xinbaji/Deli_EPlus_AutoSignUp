@echo off
rem ====== Deli EPlus AutoSignUp - run from source ======
rem Usage: double-click, or run from any cwd. Requires .venv at repo root.
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
"%PYTHON%" -m deli_eplus.gui
popd
endlocal
