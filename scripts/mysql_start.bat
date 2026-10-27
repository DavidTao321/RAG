@echo off
rem Start MySQL 8.4 in user mode (datadir D:\mysql-data, localhost only).
rem mysqld runs in background on Windows when --console is omitted.
rem Note: ASCII-only file; Chinese text in .bat breaks under cmd's GBK codepage.
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --datadir=D:\mysql-data --port=3306 --bind-address=127.0.0.1
if errorlevel 1 (
    echo MySQL failed to start - see D:\mysql-data\*.err for details
    pause
)
