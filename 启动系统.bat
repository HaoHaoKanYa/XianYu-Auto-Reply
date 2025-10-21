@echo off
chcp 65001 >nul

REM 切换到脚本所在目录
cd /d "%~dp0"

echo ========================================
echo   闲鱼自动回复系统 - 启动脚本
echo ========================================
echo.
echo 当前目录: %CD%
echo.

echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.12
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] 检查端口占用情况...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080 ^| findstr LISTENING') do (
    set PID=%%a
    goto :found_port
)
goto :no_port

:found_port
echo [警告] 检测到8080端口被进程 %PID% 占用
echo [处理] 正在停止占用端口的进程...
taskkill /F /PID %PID% >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法停止进程 %PID%，可能需要管理员权限
    echo [提示] 请右键以管理员身份运行此脚本
    pause
    exit /b 1
) else (
    echo [成功] 已停止进程 %PID%
    timeout /t 2 /nobreak >nul
)

:no_port
echo [检查] 8080端口可用

echo.
echo [3/4] 清理旧的Python进程...
taskkill /F /IM python.exe /T >nul 2>&1
if errorlevel 1 (
    echo [提示] 没有发现旧的Python进程
) else (
    echo [成功] 已清理旧的Python进程
    timeout /t 2 /nobreak >nul
)

echo.
echo [4/4] 启动系统...
echo.
echo 系统启动后将自动打开浏览器
echo 访问地址: http://localhost:8080
echo 默认账号: admin
echo 默认密码: admin123
echo.
echo 按 Ctrl+C 可以停止系统
echo ========================================
echo.

REM 在后台启动 Python 程序
start /B python Start.py

REM 等待服务启动（等待8秒）
echo 正在启动服务，请稍候...
timeout /t 8 /nobreak >nul

REM 自动打开浏览器
echo 正在打开浏览器...
start http://localhost:8080

echo.
echo ========================================
echo 系统已启动！浏览器已打开
echo 如需停止系统，请关闭此窗口
echo ========================================
echo.

REM 保持窗口打开，等待用户按键
pause
