# Windows PowerShell script to start the FastAPI backend server
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting Manufacturing Knowledge Assistant Backend       " -ForegroundColor Cyan
Write-Host " Machine Target: DEMO-CNC-01                              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Set environment
$env:PYTHONPATH = "backend;$env:PYTHONPATH"

# Check if database is seeded
if (-not (Test-Path "data\mfg_assistant.db")) {
    Write-Host "[1/2] Seeding database with synthetic demonstration corpus..." -ForegroundColor Yellow
    python scripts/seed_demo_data.py
} else {
    Write-Host "[1/2] Database found at data\mfg_assistant.db." -ForegroundColor Green
}

Write-Host "[2/2] Launching Uvicorn ASGI server on http://127.0.0.1:8000..." -ForegroundColor Green
Set-Location -Path "backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
