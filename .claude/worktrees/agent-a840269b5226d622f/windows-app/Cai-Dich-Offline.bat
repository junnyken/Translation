@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Cai dich offline - Qwen3-VL 8B
rem Chi dung Ollama tren may nay, khong dung server tu bien moi truong.
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_EXE=ollama.exe"
echo ============================================================================
echo    CAI DICH OFFLINE - QWEN3-VL 8B - MODEL qwen3-vl:8b
echo ============================================================================
echo.
echo App khong tu doi tu Gemini sang offline. Script khong tu cai Ollama.
echo Model tai lan dau khoang 6.2 GB, can Internet va du dung luong dia trong.
echo Toc do dich va RAM/VRAM can thiet phu thuoc cau hinh may va kich thuoc anh.
echo Sau khi cai xong, app se chay thu model that (khong chi kiem tra da tai model).
echo.

:find_ollama
where ollama.exe >nul 2>&1
if not errorlevel 1 goto ollama_found
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    goto ollama_found
)
goto missing_ollama

:ollama_found
"%OLLAMA_EXE%" --version
if errorlevel 1 goto cli_failed
"%OLLAMA_EXE%" list >nul
if errorlevel 1 goto server_failed
"%OLLAMA_EXE%" show qwen3-vl:8b >nul 2>&1
if not errorlevel 1 goto ready

echo Chua co model qwen3-vl:8b tren Ollama cuc bo.
choice /C YN /N /M "Ban dong y tai model qwen3-vl:8b khoang 6.2 GB bay gio? [Y/N] "
if errorlevel 2 goto cancelled
if not errorlevel 1 goto choice_failed
"%OLLAMA_EXE%" pull qwen3-vl:8b
if errorlevel 1 goto pull_failed
"%OLLAMA_EXE%" show qwen3-vl:8b >nul
if errorlevel 1 goto verify_failed

:ready
echo.
echo [OK] qwen3-vl:8b da co tren Ollama cuc bo.
echo Giu Ollama dang chay, mo Chay-App-Dich-Truyen-Windows.bat.
echo Bam "Kiem tra Qwen3-VL 8B" trong app de CHAY THU model that truoc khi dich anh.
echo Neu loi CUDA/runner, xem %%LOCALAPPDATA%%\Ollama\server.log; cap nhat driver NVIDIA va Ollama.
echo Co the tick "Chay Ollama bang CPU (cham)" trong app de kiem tra, nhung dich anh se cham hon nhieu.
echo Trong o "Bo may AI", CHON "local_gguf (Qwen3-VL 8B Offline)".
echo Gemini van la mac dinh; nut kiem tra khong tu doi bo may.
echo Chon thu muc anh co san de dich khong can tai anh qua Internet.
echo Khong can tai khoan VIP hay API key cho bo may local_gguf.
pause
exit /b 0

:missing_ollama
echo [CHUA CAI] Can tu cai Ollama tu trang chinh thuc:
echo https://ollama.com/download/windows
echo Tai va chay bo cai Windows thu cong, mo Ollama, sau do chay lai file nay.
echo Script nay KHONG tai hay chay script/bo cai tu xa.
choice /C YN /N /M "Mo trang tai Ollama chinh thuc trong trinh duyet? [Y/N] "
if errorlevel 2 goto cancelled
if not errorlevel 1 goto choice_failed
rem "start" khong dat lai errorlevel khi thanh cong; ma 1 con lai tu "choice" (Y).
start "" "https://ollama.com/download/windows"
:wait_install
echo.
echo Da yeu cau mo trang tai Ollama. Neu chua mo, tu truy cap:
echo https://ollama.com/download/windows
echo Tren trang, chon "Download manually" de tai bo cai Windows.
echo Chay bo cai vua tai, sau do mo Ollama tu Start Menu.
echo Cai xong, quay lai cua so nay va bam phim bat ky de tiep tuc buoc tai qwen3-vl:8b.
pause
where ollama.exe >nul 2>&1
if not errorlevel 1 goto find_ollama
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" goto find_ollama
echo [CHUA THAY] Chua tim thay Ollama tren may.
choice /C YN /N /M "Da cai xong va muon kiem tra lai? (N de thoat) [Y/N] "
if errorlevel 2 goto cancelled
goto wait_install

:cli_failed
echo [LOI] Khong chay duoc Ollama. Cai lai/cap nhat tai https://ollama.com/download/windows
pause
exit /b 1

:server_failed
echo [LOI] Khong ket noi duoc Ollama tai 127.0.0.1:11434.
echo Hay mo Ollama tu Start Menu, hoac chay "ollama serve", roi chay lai file nay.
pause
exit /b 1

:pull_failed
echo [LOI] Tai model that bai. Xem loi Ollama o tren; kiem tra Internet va dung luong dia.
echo Neu bao khong ho tro Qwen3-VL, cap nhat tai https://ollama.com/download/windows
echo Sau khi sua, chay lai file nay de thu tai tiep. App chua duoc chuyen sang offline.
pause
exit /b 1

:verify_failed
echo [LOI] Lenh tai da ket thuc nhung chua xac nhan duoc qwen3-vl:8b. Xem loi o tren.
pause
exit /b 1

:choice_failed
echo [LOI] Khong doc duoc xac nhan Y/N. Khong tai model.
pause
exit /b 1

:cancelled
echo Da huy. Khong tai model, khong thay doi bo may AI cua app.
pause
exit /b 0
