@echo off
setlocal
cd /d "%~dp0\.."

set "NAME=DEVHub TuningForge"
set "PYTHON_CMD=python"
if not "%~1"=="" set "PYTHON_CMD=%~1"

set "PYROOT_FILE=%TEMP%\devhub_tuningforge_python_root.txt"
"%PYTHON_CMD%" -c "import sys; print(sys.base_prefix)" > "%PYROOT_FILE%"
if errorlevel 1 (
    echo Kein ausfuehrbarer Python-Interpreter gefunden.
    exit /b %ERRORLEVEL%
)
set /p PYTHON_ROOT=<"%PYROOT_FILE%"
del "%PYROOT_FILE%" >nul 2>nul

if not defined PYTHON_ROOT (
    echo Kein ausfuehrbarer Python-Interpreter gefunden.
    exit /b 1
)

set "PYTHON_DLLS=%PYTHON_ROOT%\DLLs"
set "PYTHON_TCL=%PYTHON_ROOT%\tcl"

"%PYTHON_CMD%" -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy(); print('Tkinter/Tcl OK')"
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHON_CMD%" -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHON_CMD%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "%NAME%" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.font ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.constants ^
    --add-binary "%PYTHON_DLLS%\_tkinter.pyd;." ^
    --add-binary "%PYTHON_DLLS%\tcl86t.dll;." ^
    --add-binary "%PYTHON_DLLS%\tk86t.dll;." ^
    --add-data "%PYTHON_TCL%;tcl" ^
    --add-data "packages;packages" ^
    --add-data "profiles;profiles" ^
    --add-data "tuning;tuning" ^
    app/main.py
if errorlevel 1 exit /b %ERRORLEVEL%

set "OUTPUT_DIR=dist\%NAME%"
if not exist "%OUTPUT_DIR%\reports" mkdir "%OUTPUT_DIR%\reports"
if not exist "%OUTPUT_DIR%\logs" mkdir "%OUTPUT_DIR%\logs"

echo Portable build created in %OUTPUT_DIR%
echo Reports and logs will be written next to the executable.
exit /b 0
