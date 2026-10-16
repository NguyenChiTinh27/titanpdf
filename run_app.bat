@echo off
chcp 65001 >nul
title LUV-PDF Private Suite - Hệ Sinh Thái Xử Lý Tài Liệu
echo ====================================================================
echo      LUV-PDF PRIVATE SUITE - HỆ SINH THÁI TỰ NHIÊN (100%% OFFLINE)
echo          Hệ thống: LUV Private Ecosystem (100%% Cục bộ & Bảo mật)
echo ====================================================================
echo.
echo [*] Đang khởi động hệ sinh thái LUV-PDF...
echo [*] Đang mở trình duyệt tại: http://127.0.0.1:8888
echo.

cd /d "%~dp0"

start "" http://127.0.0.1:8888
python -m uvicorn server:app --host 127.0.0.1 --port 8888

pause
