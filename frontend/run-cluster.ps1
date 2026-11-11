# Bat lounge + 6 FE + BFF. RAG :8000 can chay san (docker compose).
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$fes = @(
    @{ dir = "chatbot-DBCL"; port = 5173; mockSources = "true" },
    @{ dir = "chatbot-qtts"; port = 5174; mockSources = "false" },
    @{ dir = "chatbot-PDT";  port = 5175; mockSources = "false" },
    @{ dir = "chatbot-PNS";  port = 5176; mockSources = "false" },
    @{ dir = "chatbot-HC";   port = 5177; mockSources = "false" },
    @{ dir = "chatbot-CTSV"; port = 5178; mockSources = "false" }
)

function Write-FeEnv([string]$path, [string]$showSources) {
    @(
        "VITE_API_URL=/api"
        "VITE_MOCK_API=false"
        "API_PROXY_TARGET=http://127.0.0.1:30957"
        "VITE_SHOW_SOURCES=$showSources"
        "VITE_AUTH_DISABLED=true"
    ) | Set-Content -LiteralPath $path -Encoding utf8
}

function Start-Window([string]$title, [string]$dir, [string]$command) {
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location -LiteralPath '$dir'; Write-Host '$title'; $command"
    )
}

foreach ($fe in $fes) {
    $dir = Join-Path $root $fe.dir
    if (-not (Test-Path (Join-Path $dir "package.json"))) { throw "Thieu $dir" }
    Set-Location $dir
    $viteOk = Test-Path (Join-Path $dir "node_modules\vite")
    if (-not $viteOk) {
        Write-Host "npm install $($fe.dir)..."
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install that bai: $($fe.dir)" }
    }
    Write-FeEnv (Join-Path $dir ".env.local") $fe.mockSources
}

Start-Window "BFF :30957" (Join-Path $root "chatbot-api") "& '$root\run-bff.ps1'"
Start-Window "Lounge :5170" (Join-Path $root "lounge") "python -m http.server 5170 --bind 127.0.0.1"
foreach ($fe in $fes) {
    $dir = Join-Path $root $fe.dir
    Start-Window "$($fe.dir) :$($fe.port)" $dir "npm run dev"
}

Write-Host ""
Write-Host "Sanh:     http://127.0.0.1:5170"
Write-Host "DBCL RAG: http://127.0.0.1:5173"
Write-Host "Can RAG API http://127.0.0.1:8000 (docker compose) cho phong DBCL."
