@echo off
echo === Installing Python dependencies for Thoth ===

echo.
echo --- Installing backend dependencies ---
python -m pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install backend dependencies
    pause
    exit /b 1
)

echo.
echo --- Installing frontend_qt dependencies ---
python -m pip install -r frontend_qt\requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install frontend_qt dependencies
    pause
    exit /b 1
)

echo.
echo --- Installing Playwright browsers ---
python -m playwright install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Playwright browsers
    pause
    exit /b 1
)

echo.
echo === All dependencies installed successfully ===
pause