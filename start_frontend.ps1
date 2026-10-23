# Windows PowerShell script to start the React + Vite frontend dashboard
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting Manufacturing AI Assistant Dashboard            " -ForegroundColor Cyan
Write-Host " Dashboard URL: http://localhost:5173                     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location -Path "frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "Launching Vite development server..." -ForegroundColor Green
npm run dev
