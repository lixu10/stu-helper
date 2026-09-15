param(
    [int]$Port = 8000,
    [switch]$Reload,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$runtimeTemp = Join-Path $projectRoot ".runtime\tmp"

Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Force -Path $runtimeTemp | Out-Null

$serviceUrl = "http://127.0.0.1:$Port"
try {
    $health = Invoke-RestMethod -Uri "$serviceUrl/health" -TimeoutSec 2
    if ($health.status -eq "ok") {
        Write-Host "Student Helper 已在运行：$serviceUrl（版本 $($health.version)）"
        return
    }
} catch {
    # No healthy Student Helper instance answered; check for an unrelated listener below.
}

$portClient = [System.Net.Sockets.TcpClient]::new()
$portInUse = $false
try {
    $portClient.Connect("127.0.0.1", $Port)
    $portInUse = $portClient.Connected
} catch [System.Net.Sockets.SocketException] {
    $portInUse = $false
} finally {
    $portClient.Dispose()
}
if ($portInUse) {
    throw "端口 $Port 已被其他程序占用。请关闭占用程序，或使用 ./scripts/start-windows.ps1 -Port 8001。"
}

# Some managed Windows environments deny writes to the user TEMP directory.
# Keep setup scratch files inside the project so venv/ensurepip remains reliable.
$env:TEMP = $runtimeTemp
$env:TMP = $runtimeTemp

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "未找到 Python。请先安装 Python 3.11 或更高版本。"
    }
    & $pythonCommand.Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "创建 Python 虚拟环境失败（退出码 $LASTEXITCODE）。"
    }
}

& $venvPython -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) {
        throw "为虚拟环境安装 pip 失败（退出码 $LASTEXITCODE）。"
    }
}

& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "安装项目依赖失败（退出码 $LASTEXITCODE）。"
}

if (-not $env:STUDENT_HELPER_DB) {
    $env:STUDENT_HELPER_DB = Join-Path $projectRoot "data\student-helper.db"
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $Port.ToString())
# Reload uses a child process and can be unavailable in managed Windows sandboxes.
# Keep the reliable single-process mode as the default; opt in with -Reload.
if ($Reload -and -not $NoReload) {
    $uvicornArgs += "--reload"
}

Write-Host "Student Helper 正在启动：$serviceUrl"
& $venvPython @uvicornArgs
if ($LASTEXITCODE -ne 0) {
    throw "Student Helper 退出（退出码 $LASTEXITCODE）。"
}
