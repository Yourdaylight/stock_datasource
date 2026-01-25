@echo off
REM Restart backend and frontend services (Windows Batch version)
REM Usage: restart.bat [start|stop|restart]

setlocal enabledelayedexpansion

set ACTION=%1
if "%ACTION%"=="" set ACTION=restart

REM Get script directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set LOG_DIR=%SCRIPT_DIR%\logs
set PID_DIR=%LOG_DIR%\pids
set BACKEND_PID_FILE=%PID_DIR%\backend.pid
set FRONTEND_PID_FILE=%PID_DIR%\frontend.pid

REM Create directories
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

REM ========================================
REM Stop services
REM ========================================
:stop_services
echo [1/4] 停止现有进程...

REM Stop by PID file
if exist "%BACKEND_PID_FILE%" (
    set /p BACKEND_PID=<%BACKEND_PID_FILE%
    taskkill /F /PID !BACKEND_PID! >nul 2>&1
    del "%BACKEND_PID_FILE%" >nul 2>&1
)

if exist "%FRONTEND_PID_FILE%" (
    set /p FRONTEND_PID=<%FRONTEND_PID_FILE%
    taskkill /F /PID !FRONTEND_PID! >nul 2>&1
    del "%FRONTEND_PID_FILE%" >nul 2>&1
)

REM Stop by port (backend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Stop by port (frontend - common ports)
for %%p in (3000 3001 3002 3003 3004 3005 5173) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING"') do (
        for /f "tokens=1" %%x in ('tasklist /FI "PID eq %%a" ^| findstr /i "node"') do (
            taskkill /F /PID %%a >nul 2>&1
        )
    )
)

echo.

if "%ACTION%"=="stop" (
    echo ==========================================
    echo   已停止
    echo ==========================================
    goto :end
)

REM ========================================
REM Prepare environment
REM ========================================
:prepare_env
echo [2/4] 准备环境...
echo   [OK] 日志目录已准备
echo.

REM ========================================
REM Start backend
REM ========================================
:start_backend
echo [3/4] 启动后端服务...
cd /d "%SCRIPT_DIR%"

set BACKEND_LOG=%LOG_DIR%\backend.log
start /B "" cmd /c "uv run python -m stock_datasource.services.http_server > %BACKEND_LOG% 2>&1"

REM Get the PID of the started process
timeout /t 2 >nul
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /i "python.exe"') do (
    set BACKEND_PID=%%~a
)
echo !BACKEND_PID! > "%BACKEND_PID_FILE%"
echo   后端PID: !BACKEND_PID!

REM Wait for backend to start (max 150 seconds)
set MAX_WAIT=150
set /a COUNT=0

:wait_backend
set /a COUNT+=1
if !COUNT! gtr %MAX_WAIT% (
    echo   [ERROR] 后端启动超时（已等待 %MAX_WAIT%s）
    echo   查看日志: type %BACKEND_LOG%
    exit /b 1
)

timeout /t 1 >nul

REM Check if backend is running
curl -s http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] 后端已启动 (http://0.0.0.0:8000)
    echo.
    goto :start_frontend
)

goto :wait_backend

REM ========================================
REM Start frontend
REM ========================================
:start_frontend
echo [4/4] 启动前端服务...
cd /d "%SCRIPT_DIR%\frontend"

set FRONTEND_LOG=%LOG_DIR%\frontend.log
start /B "" cmd /c "npm run dev > %FRONTEND_LOG% 2>&1"

REM Get the PID of the started process
timeout /t 2 >nul
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /FO CSV ^| findstr /i "node.exe"') do (
    set FRONTEND_PID=%%~a
)
echo !FRONTEND_PID! > "%FRONTEND_PID_FILE%"
echo   前端PID: !FRONTEND_PID!

REM Wait for frontend to start and detect port
set FRONTEND_PORT=
set /a COUNT=0

:wait_frontend
set /a COUNT+=1
if !COUNT! gtr 25 (
    echo   [WARN] 前端启动较慢，请稍后检查
    goto :finish
)

timeout /t 1 >nul

REM Check common frontend ports
for %%p in (3000 3001 3002 3003 3004 3005 5173) do (
    netstat -ano | findstr ":%%p.*LISTENING" >nul 2>&1
    if !errorlevel! equ 0 (
        set FRONTEND_PORT=%%p
        goto :frontend_found
    )
)

goto :wait_frontend

:frontend_found
if not "%FRONTEND_PORT%"=="" (
    echo   [OK] 前端已启动 (http://0.0.0.0:%FRONTEND_PORT%)
)

:finish
echo.
echo ==========================================
echo   OK - 所有服务已成功重启！
echo ==========================================
echo.
echo 后端 API: http://0.0.0.0:8000
echo 前端界面: http://0.0.0.0:%FRONTEND_PORT:=-5173%
echo.
echo 查看日志:
echo   后端: type %BACKEND_LOG%
echo   前端: type %FRONTEND_LOG%
echo.
echo 停止服务:
echo   停止全部: %~nx0 stop
echo.

:end
endlocal
