@echo off
REM Quick start script - Restarts all services with minimal output

echo Starting Stock DataSource services...
echo.

REM Stop existing services
echo Stopping existing services...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 >nul

REM Start backend
echo Starting backend service...
cd /d "%~dp0"
start /MIN cmd /c "uv run python -m stock_datasource.services.http_server"
echo Backend starting... (port 8000)

REM Start frontend
echo Starting frontend service...
cd frontend
start /MIN cmd /c "npm run dev"
cd ..
echo Frontend starting... (port 3000-3005 or 5173)
echo.

echo ========================================
echo Services are starting in background...
echo ========================================
echo.
echo Please wait 30-60 seconds for services to fully start.
echo.
echo Backend API: http://localhost:8000
echo Frontend: http://localhost:3000 (or other available port)
echo.
echo To view logs, check the terminal windows.
echo To stop services, close the terminal windows or use:
echo   taskkill /F /IM python.exe /IM node.exe
echo.

pause
