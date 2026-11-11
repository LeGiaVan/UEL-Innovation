$ErrorActionPreference = "Stop"
$fe = Join-Path $PSScriptRoot "chatbot-DBCL"
Set-Location $fe
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path ".env.local")) { Copy-Item ".env.example" ".env.local" }
Write-Host "Giao dien http://127.0.0.1:5173"
npm run dev
