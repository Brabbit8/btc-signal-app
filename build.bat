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
echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

REM Install PyInstaller
echo [2/4] Installing PyInstaller...
pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller install failed.
    pause
    exit /b 1
)

REM Clean old build
echo [3/4] Cleaning old build...
if exist dist\ rd /s /q dist
if exist build\ rd /s /q build

REM Build
echo [4/4] Building btc-signal-app.exe...
pyinstaller --onefile --console --name btc-signal-app ^
    --add-data "btc_signal_config.example.json;." ^
    --add-data "skills;skills" ^
    --hidden-import skills ^
    --hidden-import skills.market_data ^
    --hidden-import skills.technical ^
    --hidden-import skills.sentiment ^
    --hidden-import skills.trading_plan ^
    --hidden-import config_manager ^
    --hidden-import ai_client ^
    --hidden-import btc_signal_bot ^
    --hidden-import btc_strategy_adaptor ^
    main.py
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
