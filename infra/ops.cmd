@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%SCRIPT_DIR%ops.py" %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python "%SCRIPT_DIR%ops.py" %*
  exit /b %errorlevel%
)

echo [ERROR] Python 3.10+ not found in PATH. Please install Python 3 first.
exit /b 1
