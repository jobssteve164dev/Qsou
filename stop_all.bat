@echo off
echo ========================================
echo 停止所有Qsou开发环境服务
echo ========================================
echo.

REM 调用dev.sh的stop命令
echo 正在停止开发环境...
bash dev.sh stop 2>nul

REM 额外确保日志收集器被停止
echo.
echo 清理日志收集器进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *unified_logger*" 2>nul
for /f "tokens=2" %%i in ('tasklist ^| findstr unified_logger') do (
    taskkill /F /PID %%i 2>nul
)

REM 停止其他可能残留的进程
echo 清理其他进程...
taskkill /F /IM node.exe /T 2>nul
taskkill /F /IM npm.cmd /T 2>nul
taskkill /F /IM celery.exe /T 2>nul

REM 清理PID文件
echo 清理PID文件...
if exist pids (
    del /Q pids\*.pid 2>nul
)

echo.
echo ========================================
echo 所有服务已停止
echo ========================================
pause
