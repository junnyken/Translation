@echo off
chcp 65001 >nul
title Manga / Manhwa Video Review Studio v1.0
cd /d "%~dp0"
python app_video_review_studio.py
if errorlevel 1 (
    echo.
    echo [LOI] Vui long kiem tra Python tren may tinh Windows cua ban.
    pause
)
