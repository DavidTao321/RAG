@echo off
rem Stop MySQL. Root password is read from backend\.env (MYSQL_ROOT_PASSWORD) - never hardcoded here.
rem Note: ASCII-only file; Chinese text in .bat breaks under cmd's GBK codepage.
rem %~dp0 = this script's folder, so the .env path works no matter where cmd is invoked from
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0..\backend\.env") do (
    if "%%a"=="MYSQL_ROOT_PASSWORD" set "MYSQL_ROOT_PASSWORD=%%b"
)
if not defined MYSQL_ROOT_PASSWORD (
    echo MYSQL_ROOT_PASSWORD not found in backend\.env - cannot stop MySQL
    pause
    exit /b 1
)
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqladmin.exe" -u root -p%MYSQL_ROOT_PASSWORD% shutdown
