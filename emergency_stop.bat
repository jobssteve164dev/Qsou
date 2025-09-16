@echo off
echo ========================================
echo 紧急停止所有开发环境进程
echo ========================================
echo.

echo 停止Node.js进程...
taskkill /F /IM node.exe /T 2>nul
taskkill /F /IM npm.cmd /T 2>nul

echo 停止Python进程...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
taskkill /F /IM celery.exe /T 2>nul

echo 停止Java进程（Elasticsearch）...
taskkill /F /IM java.exe /T 2>nul

echo 停止Qdrant进程...
taskkill /F /IM qdrant.exe /T 2>nul

echo 停止Git Bash进程...
taskkill /F /IM bash.exe /T 2>nul
taskkill /F /IM sh.exe /T 2>nul

echo 停止tail进程...
taskkill /F /IM tail.exe /T 2>nul

echo 清理PID文件...
if exist pids (
    del /Q pids\*.pid 2>nul
)

echo.
echo ========================================
echo 所有进程已停止
echo ========================================
echo.
echo 建议操作：
echo 1. 检查内存使用: taskmgr
echo 2. 修改配置文件 dev.local：
echo    - 设置 ENABLE_UNIFIED_LOG=false
echo    - 减小 UNIFIED_LOG_MAX_LINES=10000
echo 3. 重新启动服务: dev.sh start
echo.
pause
