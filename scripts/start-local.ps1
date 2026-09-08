param([switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$apiDirectory = Join-Path $projectRoot 'apps\api'
$pythonPath = Join-Path $apiDirectory '.venv\Scripts\python.exe'
$logDirectory = Join-Path $projectRoot 'data\logs'

function Wait-LocalUrl([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return }
        } catch {}
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url. Check data\logs."
}

function Test-ProjectListener([int]$Port, [string]$ProcessPattern) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if (!$listeners.Count) { return $false }
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if (!$process.CommandLine -or $process.CommandLine -notmatch [regex]::Escape($projectRoot) -or $process.CommandLine -notmatch $ProcessPattern) {
            throw "Port $Port is occupied by another process. No process was stopped."
        }
    }
    return $true
}

try {
    foreach ($command in @('node','npm.cmd','docker')) {
        if (!(Get-Command $command -ErrorAction SilentlyContinue)) { throw "Missing command: $command. See docs\LOCAL_USE.md." }
    }
    foreach ($path in @($pythonPath, (Join-Path $apiDirectory '.env'), (Join-Path $projectRoot 'node_modules\next\package.json'))) {
        if (!(Test-Path -LiteralPath $path)) { throw "Missing local setup: $path. See docs\LOCAL_USE.md." }
    }
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    Push-Location $projectRoot
    try {
        Write-Host 'Starting PostgreSQL and Redis (existing data is preserved)...'
        & docker compose up -d --wait --wait-timeout 60 postgres redis
        if ($LASTEXITCODE -ne 0) { throw 'Docker is not ready. Open Docker Desktop, then retry. Do not reset its data.' }
        if (!(Test-ProjectListener 8000 'uvicorn')) {
            Start-Process -FilePath $pythonPath -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $apiDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'api-out.log') -RedirectStandardError (Join-Path $logDirectory 'api-error.log') | Out-Null
        }
        Wait-LocalUrl 'http://127.0.0.1:8000/health'
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 5
        if ($health.service -ne 'creator-radar-api') { throw 'The API port is serving an unexpected application.' }
        # Verify database-backed routes, not just the process health endpoint.
        Wait-LocalUrl 'http://127.0.0.1:8000/api/v1/works' 15
        if (!(Test-ProjectListener 3000 'next')) {
            Start-Process -FilePath 'cmd.exe' -ArgumentList '/d /c npm.cmd run dev' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'web-out.log') -RedirectStandardError (Join-Path $logDirectory 'web-error.log') | Out-Null
        }
        Wait-LocalUrl 'http://127.0.0.1:3000/today'
        Wait-LocalUrl 'http://127.0.0.1:3000/api/works' 15
        Write-Host 'Creator Radar is ready: http://127.0.0.1:3000/today'
        Write-Host 'Logs: data\logs. This starts local development services, not a public deployment.'
        if ($OpenBrowser) { Start-Process 'http://127.0.0.1:3000/today' }
    } finally { Pop-Location }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
