@echo off
chcp 65001 >nul
title Manga / Manhwa Video Review Studio v1.0
cd /d "%~dp0"
echo [1/2] Dang kiem tra goi Giong Doc AI & Bo Dong Goi Video MP4...
python -c "import PIL, edge_tts, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    echo Dang tu dong cai dat bo Giong Doc AI & Nhan Render MP4 lan dau...
    python -m pip install --upgrade Pillow edge-tts imageio-ffmpeg
)
echo [2/2] Dang khoi dong Giao dien Studio...
python app_video_review_studio.py
if errorlevel 1 (
    echo.
    echo [LOI] Vui long kiem tra Python tren may tinh Windows cua ban.
    pause
)
