@echo off
title Browser-Use Web UI
echo ========================================================
echo Starting Browser-Use Web UI (Microsoft Edge)...
echo ========================================================
if exist .\venv\Scripts\python.exe (
    .\venv\Scripts\python.exe web_ui.py
) else (
    python web_ui.py
)
pause
