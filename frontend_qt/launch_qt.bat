@echo off
REM Launcher for HAHS AI Call Assistant Qt Frontend
cd /d "%~dp0"
cd ..
call .venv\Scripts\activate.bat
python frontend_qt\main.py
pause
