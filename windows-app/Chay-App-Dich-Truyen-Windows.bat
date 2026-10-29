@echo off
chcp 65001 >nul
title Manga Studio Pro - App Dich Truyen Tu Dong Theo Link (Windows)
cd /d "%~dp0"
echo ============================================================================
echo    MANGA STUDIO PRO - APP DICH TRUYEN TU DONG THEO LINK VA CHIA CHAPTER
echo ============================================================================
echo.
python -c "import PIL, rapidocr_onnxruntime" >nul 2>&1
if errorlevel 1 (
    echo [1/2] Dang tu dong cai dat Loi Nhan Dien Da Ngon Ngu va Xu Ly Anh lan dau...
    python -m pip install --upgrade Pillow rapidocr-onnxruntime --quiet
)
echo [2/2] Dang khoi dong giao dien Manga Studio Windows...
python "%~dp0app_dich_truyen_windows.py"
if errorlevel 1 (
    echo.
    echo [LOI] Khong khoi dong duoc giao dien. Vui long kiem tra Python tren may.
    pause
)

