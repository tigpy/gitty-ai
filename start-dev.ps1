# GITTY AI - Local Development Startup Script (Windows PowerShell)
# This script starts the required infrastructure and application services for local development.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Starting GITTY AI (Local Developer Mode)        " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Check / Start Docker Infrastructure (Redis, RabbitMQ, Qdrant)
Write-Host "`n[1/4] Checking Docker infrastructure..." -ForegroundColor Yellow
try {
    docker ps > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Starting Redis, RabbitMQ, and Qdrant containers..."
        docker compose -f "$ProjectRoot\infrastructure\compose\docker-compose.yml" up -d redis rabbitmq qdrant
    } else {
        Write-Host "Warning: Docker is not running or not found. Ensure Redis (6379), RabbitMQ (5672), and Qdrant (6333) are accessible locally." -ForegroundColor Red
    }
} catch {
    Write-Host "Notice: Docker check skipped ($_.Exception.Message)" -ForegroundColor Gray
}

# 2. Start Celery Worker
Write-Host "`n[2/4] Starting Celery Worker (solo pool for Windows)..." -ForegroundColor Yellow
$workerProcess = Start-Process -FilePath "$ProjectRoot\venv\Scripts\celery.exe" `
    -ArgumentList "-A", "apps.worker.worker_app", "worker", "--loglevel=info", "-P", "solo" `
    -WorkingDirectory $ProjectRoot `
    -PassThru

Write-Host "Celery Worker running (PID: $($workerProcess.Id))" -ForegroundColor Green

# 3. Start FastAPI Server
Write-Host "`n[3/4] Starting FastAPI Server on 127.0.0.1:8000..." -ForegroundColor Yellow
$apiProcess = Start-Process -FilePath "$ProjectRoot\venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "$ProjectRoot\apps\api-gateway" `
    -PassThru

Write-Host "FastAPI Server running (PID: $($apiProcess.Id))" -ForegroundColor Green

# 4. Start Frontend
Write-Host "`n[4/4] Starting Frontend Vite Dev Server..." -ForegroundColor Yellow
$frontendProcess = Start-Process -FilePath "npm" `
    -ArgumentList "--prefix", "apps/frontend", "run", "dev" `
    -WorkingDirectory $ProjectRoot `
    -PassThru

Write-Host "Frontend running (PID: $($frontendProcess.Id))" -ForegroundColor Green

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host " GITTY AI is ready for local development!         " -ForegroundColor Cyan
Write-Host " Frontend: http://localhost:5173                  " -ForegroundColor Green
Write-Host " Backend:  http://127.0.0.1:8000                  " -ForegroundColor Green
Write-Host " API Docs: http://127.0.0.1:8000/docs             " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "`nTo stop all processes, run:" -ForegroundColor Yellow
Write-Host "Stop-Process -Id $($workerProcess.Id), $($apiProcess.Id), $($frontendProcess.Id) -Force" -ForegroundColor White

