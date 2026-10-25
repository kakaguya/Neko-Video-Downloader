@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1

rem Keep the project environment independent of an activated Python/Conda session.
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"

if exist ".venv\Scripts\python.exe" goto check_environment

echo [Neko] Creating the project virtual environment...
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto create_with_py
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto create_with_python
echo [ERROR] Python 3.10 or newer is required.
echo Install Python from https://www.python.org/downloads/ and enable Add Python to PATH.
goto failed

:create_with_py
py -3 -m venv .venv
if errorlevel 1 goto environment_failed
goto install_dependencies

:create_with_python
python -m venv .venv
if errorlevel 1 goto environment_failed
goto install_dependencies

:check_environment
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto environment_failed
".venv\Scripts\python.exe" -c "from PyQt5 import QtWidgets; import yt_dlp; from importlib.metadata import version; version('yt-dlp-ejs'); import pip" >nul 2>&1
if errorlevel 1 goto install_dependencies
goto launch

:install_dependencies
echo [Neko] Installing requirements.txt. Internet access is needed for this step.
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" -c "from PyQt5 import QtWidgets; import yt_dlp; from importlib.metadata import version; version('yt-dlp-ejs')"
if errorlevel 1 goto install_failed

:launch
if /i "%~1"=="--setup" goto ready
".venv\Scripts\python.exe" run.py
set "NEKO_EXIT_CODE=%errorlevel%"
if not "%NEKO_EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] The application exited with code %NEKO_EXIT_CODE%.
  pause
)
popd
exit /b %NEKO_EXIT_CODE%

:ready
echo [Neko] Environment is ready. Double-click run.bat to start.
popd
exit /b 0

:environment_failed
echo [ERROR] Could not create or use .venv. Python 3.10 or newer is required.
echo If this folder was moved, rename .venv and run this script again to recreate it.
goto failed

:install_failed
echo [ERROR] Dependency installation failed. Check your network and try run.bat again.
echo You can also run: .venv\Scripts\python.exe -m pip install -r requirements.txt

:failed
pause
popd
exit /b 1
