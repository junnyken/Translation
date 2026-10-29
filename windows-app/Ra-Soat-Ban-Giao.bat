@echo off
chcp 65001 >nul
python "%~dp0review_delivery.py" %*
exit /b %errorlevel%
