@echo off
chcp 65001 >nul
title Manga/Manhwa Video Review Studio v1.0 - Bien Kich, Nhan Dien Nhan Vat va Long Tieng MP4
cd /d "%~dp0"
echo ================================================================================
echo    MANGA / MANHWA VIDEO REVIEW STUDIO v1.0 - BIEN KICH AI ^& XUAT VIDEO MP4
echo ================================================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;%PATH%"
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
)

where python >nul 2>&1
if errorlevel 1 (
    echo [0/3] May tinh chua cai Python. Dang tu dong tai va cai dat Python 3.11 chuan ^(25MB^)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile \"$env:TEMP\py311_setup.exe\"; Start-Process -FilePath \"$env:TEMP\py311_setup.exe\" -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1' -Wait"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
)

python -c "import PIL, edge_tts, imageio_ffmpeg, rapidocr_onnxruntime" >nul 2>&1
if errorlevel 1 (
    echo [1/3] Dang cai dat Bo Long Tieng Neural Viet Nam, OCR va Bo Dung Video MP4...
    python -m pip install --upgrade Pillow edge-tts imageio-ffmpeg rapidocr-onnxruntime --quiet
)
where ollama >nul 2>&1
if not errorlevel 1 (
    ollama list | findstr /i "qwen" >nul 2>&1
    if errorlevel 1 (
        echo [2/3] Dang tai Bo May AI Bien Kich ^(qwen3-vl:8b^)...
        ollama pull qwen3-vl:8b
    )
)
echo [3/3] Dang khoi dong giao dien Manga/Manhwa Video Review Studio...
python "%~dp0app_video_review_studio.py"
if errorlevel 1 (
    echo.
    echo [LOI] Khong khoi dong duoc giao dien. Vui long kiem tra ket noi mang de tai moi truong Python.
    pause
)
