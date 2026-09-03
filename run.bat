@echo off
title HiveTrust AI - Flask
echo ==========================================
echo        HiveTrust AI - Local Flask
echo ==========================================
echo.
py -3.14 -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)
echo.
echo Starting HiveTrust AI...
echo Open: http://127.0.0.1:5000
echo Press CTRL+C to stop.
echo.
py -3.14 app.py
pause
