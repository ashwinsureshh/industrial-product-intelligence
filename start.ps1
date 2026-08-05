<#
    One-command startup for Windows.

    Runs entirely in demo mode by default: no API key, no network calls, no cost.
    Open http://localhost:5173 once both servers report ready.
#>

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

Write-Host "Industrial Product Intelligence" -ForegroundColor Cyan
Write-Host "-------------------------------`n"

# --- backend -----------------------------------------------------------------
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Push-Location "$root\backend"
python -m pip install -q -r requirements.txt
Pop-Location

Write-Host "Starting API on http://127.0.0.1:8000 ..." -ForegroundColor Yellow
$api = Start-Process -PassThru -WorkingDirectory "$root\backend" `
    -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"

# --- frontend ----------------------------------------------------------------
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing Node dependencies (first run only)..." -ForegroundColor Yellow
    Push-Location "$root\frontend"
    npm install
    Pop-Location
}

Write-Host "Starting UI on http://localhost:5173 ...`n" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor DarkGray

try {
    Push-Location "$root\frontend"
    npm run dev
}
finally {
    Pop-Location
    if ($api -and -not $api.HasExited) {
        Write-Host "`nStopping API..." -ForegroundColor DarkGray
        Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    }
}
