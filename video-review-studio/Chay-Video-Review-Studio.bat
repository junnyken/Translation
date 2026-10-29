@echo off
chcp 65001 >nul
title Manga / Manhwa Video Review Studio v1.0
cd /d "%~dp0"
echo [1/3] Dang kiem tra goi Giong Doc AI, OCR & Bo Dong Goi Video MP4...
python -c "import PIL, edge_tts, imageio_ffmpeg, rapidocr_onnxruntime" >nul 2>&1
if errorlevel 1 (
    echo Dang tu dong cai dat bo Giong Doc AI, OCR & Nhan Render MP4 lan dau...
    python -m pip install --upgrade Pillow edge-tts imageio-ffmpeg rapidocr-onnxruntime --quiet
)
where ollama >nul 2>&1
if not errorlevel 1 (
    ollama list | findstr /i "qwen" >nul 2>&1
    if errorlevel 1 (
        echo [2/3] Dang tai Bo May AI Bien Kich Thi Giac cho may moi...
        ollama pull qwen3-vl:8b
    )
)
echo [3/3] Dang khoi dong Giao dien Studio...
python app_video_review_studio.py
if errorlevel 1 (
    echo.
    echo [LOI] Vui long kiem tra Python tren may tinh Windows cua ban.
    pause
)

