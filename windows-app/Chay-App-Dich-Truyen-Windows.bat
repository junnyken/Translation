@echo off
chcp 65001 >nul
title Manga Studio Pro - App Dich Truyen Tu Dong Theo Link (Windows)
echo ============================================================================
echo    MANGA STUDIO PRO - APP DICH TRUYEN TU DONG THEO LINK VA CHIA CHAPTER
echo ============================================================================
echo.
python -c "import PIL" 2>nul
if errorlevel 1 (
    echo [1/2] Dang cai dat thu vien xu ly anh Pillow cho Windows...
    pip install Pillow --quiet
)
echo [2/2] Dang khoi dong giao dien Manga Studio Windows...
start "" pythonw "%~dp0app_dich_truyen_windows.py" || python "%~dp0app_dich_truyen_windows.py"
