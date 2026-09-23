# GITTY AI - Stop Local Development Processes (Windows PowerShell)

Write-Host "Stopping GITTY AI background processes..." -ForegroundColor Yellow

# Kill Celery processes
Get-Process celery -ErrorAction SilentlyContinue | Stop-Process -Force
# Kill Uvicorn processes listening on 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.OwningProcess -gt 0) {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "GITTY AI processes stopped." -ForegroundColor Green

