@echo off
title LUV-PDF - Trinh Quan Ly & Tao Ma Ban Quyen Doanh Nghiep
color 0B
chcp 65001 >nul
cls

echo ======================================================================
echo          LUV-PDF PRIVATE SUITE - TRINH QUAN LY BAN QUYEN
echo          Tao Ma Ban Quyen • Quan Ly Thiet Bi • Bao Mat Tuyet Doi
echo ======================================================================
echo.

if exist "dist\LUV_License_Manager.exe" (
    echo [*] Dang khoi chay Trinh Quan Ly Ban Quyen LUV...
    start "" "dist\LUV_License_Manager.exe"
) else if exist "LUV_License_Manager.exe" (
    echo [*] Dang khoi chay Trinh Quan Ly Ban Quyen LUV...
    start "" "LUV_License_Manager.exe"
) else (
    echo [*] Khoi chay bang Python Engine...
    python license_manager_app.py
)

echo [*] Chuong trinh dang chay. Cua so nay se tu dong dong sau 3 giay.
timeout /t 3 /nobreak >nul
exit
