@echo off
REM ============================================================
REM  Fuzhou Mahjong — Windows build script
REM  Run this once on your Windows machine to produce the .exe.
REM  Requires: Python 3.10+ in PATH  (python.org/downloads)
REM ============================================================

echo.
echo  Fuzhou Mahjong — building Windows app...
echo  ==========================================
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Download it from https://python.org/downloads
    echo  Make sure to tick "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Install / upgrade required packages
echo  [1/3] Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install pygame>=2.5 websockets>=12.0 pillow>=10.0 pyinstaller --quiet
if errorlevel 1 (
    echo  ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)

REM Build the app
echo  [2/3] Building FuzhouMahjong.exe  ^(this takes 1-2 minutes^)...
python -m PyInstaller fuzhou_mahjong.spec --noconfirm
if errorlevel 1 (
    echo  ERROR: PyInstaller build failed. See output above for details.
    pause
    exit /b 1
)

REM Done
echo.
echo  [3/3] Done!
echo.
echo  Your app is in:  dist\FuzhouMahjong\
echo.
echo  To share with friends:
echo    1. Zip the entire  dist\FuzhouMahjong\  folder
echo    2. Send them the zip — they just extract and double-click FuzhouMahjong.exe
echo    3. No Python or terminal required on their end!
echo.
echo  To host online across the internet, one player runs the app,
echo  clicks "Host a Game", then shares their IP (or use ngrok / Tailscale).
echo.
pause
