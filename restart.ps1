# Restart backend and frontend services (Windows version)
# Usage: .\restart.ps1 [start|stop|restart]

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("start", "stop", "restart")]
    [string]$Action = "restart"
)

# 颜色设置
function Write-Color {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$PidDir = Join-Path $LogDir "pids"
$BackendPidFile = Join-Path $PidDir "backend.pid"
$FrontendPidFile = Join-Path $PidDir "frontend.pid"

# 创建目录
if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
if (!(Test-Path $PidDir)) { New-Item -ItemType Directory -Path $PidDir -Force | Out-Null }

# 检查进程是否存在
function Test-ProcessExists {
    param([int]$Pid)

    try {
        $process = Get-Process -Id $Pid -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

# 停止指定进程
function Stop-ProcessSafe {
    param([int]$Pid, [string]$Label)

    if (!(Test-ProcessExists -Pid $Pid)) {
        return
    }

    Write-Color "  停止 $Label (PID: $Pid)" Yellow

    try {
        # 先尝试优雅停止
        Stop-Process -Id $Pid -Force -ErrorAction Stop

        # 等待进程退出
        for ($i = 0; $i -lt 10; $i++) {
            Start-Sleep -Milliseconds 500
            if (!(Test-ProcessExists -Pid $Pid)) {
                return
            }
        }
    } catch {
        Write-Color "    停止失败: $_" Red
    }
}

# 通过 PID 文件停止服务
function Stop-ByPidFile {
    param([string]$PidFile, [string]$Label)

    if (!(Test-Path $PidFile)) {
        return
    }

    $pid = [int](Get-Content $PidFile -ErrorAction SilentlyContinue)

    if ($pid -eq 0) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    if (Test-ProcessExists -Pid $pid) {
        Stop-ProcessSafe -Pid $pid -Label $Label
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# 通过端口停止服务
function Stop-ByPort {
    param([int]$Port, [string]$Label)

    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($connections) {
            foreach ($conn in $connections) {
                $pid = $conn.OwningProcess
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Color "  端口 $Port 被占用 (PID: $pid, 进程: $($process.ProcessName))" Yellow
                    Stop-ProcessSafe -Pid $pid -Label $Label
                }
            }
        }
    } catch {
        # 端口可能未被占用
    }
}

function Print-Header {
    Write-Color "==========================================" Cyan
    Write-Color "  重启服务" Cyan
    Write-Color "==========================================" Cyan
    Write-Host ""
}

function Stop-Services {
    Write-Color "[1/4] 停止现有进程..." Yellow

    # 通过 PID 文件停止
    Stop-ByPidFile -PidFile $BackendPidFile -Label "后端服务"
    Stop-ByPidFile -PidFile $FrontendPidFile -Label "前端服务"

    # 通过端口兜底停止
    Stop-ByPort -Port 8000 -Label "后端服务"

    foreach ($port in @(3000, 3001, 3002, 3003, 3004, 3005, 5173)) {
        Stop-ByPort -Port $port -Label "前端服务"
    }

    Write-Host ""
}

function Prepare-Env {
    Write-Color "[2/4] 准备环境..." Yellow
    Write-Color "  ✓ 日志目录已准备" Green
    Write-Host ""
}

function Start-Backend {
    Write-Color "[3/4] 启动后端服务..." Yellow

    $OldPath = Get-Location
    Set-Location $ScriptDir

    try {
        $BackendLog = Join-Path $LogDir "backend.log"

        # 启动后端服务
        $process = Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "stock_datasource.services.http_server" `
            -RedirectStandardOutput $BackendLog `
            -RedirectStandardError $BackendLog `
            -WindowStyle Hidden `
            -PassThru

        $BackendPid = $process.Id
        $BackendPid | Out-File -FilePath $BackendPidFile -Encoding utf8
        Write-Color "  后端PID: $BackendPid" Cyan

        # 等待后端启动（最多 150 秒）
        $MaxWait = 150
        for ($i = 1; $i -le $MaxWait; $i++) {
            Start-Sleep -Seconds 1

            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8000/health" `
                    -TimeoutSec 2 `
                    -UseBasicParsing `
                    -ErrorAction Stop

                if ($response.StatusCode -eq 200) {
                    Write-Color "  ✓ 后端已启动 (http://0.0.0.0:8000)" Green
                    Write-Host ""
                    return
                }
            } catch {
                # 继续等待
            }

            if ($i -eq $MaxWait) {
                Write-Color "  ✗ 后端启动超时（已等待 ${MaxWait}s）" Red
                Write-Color "  查看日志: Get-Content $BackendLog -Wait" Yellow
                exit 1
            }
        }
    } finally {
        Set-Location $OldPath
    }
}

function Start-Frontend {
    Write-Color "[4/4] 启动前端服务..." Yellow

    $OldPath = Get-Location
    $FrontendDir = Join-Path $ScriptDir "frontend"
    Set-Location $FrontendDir

    try {
        $FrontendLog = Join-Path $LogDir "frontend.log"

        # 启动前端服务
        $process = Start-Process -FilePath "npm" -ArgumentList "run", "dev" `
            -RedirectStandardOutput $FrontendLog `
            -RedirectStandardError $FrontendLog `
            -WindowStyle Hidden `
            -PassThru

        $FrontendPid = $process.Id
        $FrontendPid | Out-File -FilePath $FrontendPidFile -Encoding utf8
        Write-Color "  前端PID: $FrontendPid" Cyan

        # 等待前端启动并获取实际端口
        $FrontendPort = ""
        for ($i = 1; $i -le 25; $i++) {
            Start-Sleep -Seconds 1

            foreach ($port in @(3000, 3001, 3002, 3003, 3004, 3005, 5173)) {
                try {
                    $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
                    if ($connection) {
                        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
                        if ($process -and $process.Id -eq $FrontendPid) {
                            $FrontendPort = $port
                            break
                        }
                    }
                } catch {
                    # 继续检查
                }
            }

            if ($FrontendPort) {
                break
            }

            if ($i -eq 25) {
                Write-Color "  ⚠ 前端启动较慢，请稍后检查" Yellow
            }
        }

        if ($FrontendPort) {
            Write-Color "  ✓ 前端已启动 (http://0.0.0.0:$FrontendPort)" Green
        }

        Write-Host ""

        # 完成
        Write-Color "==========================================" Cyan
        Write-Color "  ✓ 所有服务已成功重启！" Green
        Write-Color "==========================================" Cyan
        Write-Host ""
        Write-Color "后端 API: http://0.0.0.0:8000" Cyan
        Write-Color "前端界面: http://0.0.0.0:$($FrontendPort -replace '^$', '5173')" Cyan
        Write-Host ""
        Write-Color "查看日志:" Cyan
        Write-Host "  后端: Get-Content $BackendLog -Wait"
        Write-Host "  前端: Get-Content $FrontendLog -Wait"
        Write-Host ""
        Write-Color "停止服务:" Cyan
        Write-Host "  停止全部: .\restart.ps1 stop"
        Write-Host ""

    } finally {
        Set-Location $OldPath
    }
}

# 主逻辑
Print-Header

switch ($Action) {
    "stop" {
        Stop-Services
        Write-Color "✓ 已停止" Green
    }
    "start" {
        Prepare-Env
        Start-Backend
        Start-Frontend
    }
    "restart" {
        Stop-Services
        Prepare-Env
        Start-Backend
        Start-Frontend
    }
}
