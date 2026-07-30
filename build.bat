@echo off
echo === BTC Signal App Builder ===
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

REM Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

REM Install PyInstaller
echo [2/3] Installing PyInstaller...
pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller install failed.
    pause
    exit /b 1
)

REM Build
echo [3/3] Building btc-signal-app.exe...
pyinstaller --onefile --console --name btc-signal-app main.py
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo === Build complete! ===
echo btc-signal-app.exe is in the dist\ folder.
echo.
pause
