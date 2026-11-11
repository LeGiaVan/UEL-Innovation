# Cau noi FE GitHub -> RAG :8000. Chay tu bat ky thu muc nao.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$bff = Join-Path $PSScriptRoot "chatbot-api"
$ragEnv = Join-Path $root ".env"
if (-not (Test-Path $ragEnv)) { throw "Khong thay $ragEnv — can file .env cua RAG." }

$key = $null
foreach ($line in Get-Content -LiteralPath $ragEnv -Encoding utf8) {
    if ($line -match '^\s*APP_API_KEY\s*=\s*(.+)\s*$') {
        $key = $Matches[1].Trim().Trim('"').Trim("'")
        break
    }
}
if (-not $key) { throw "Trong .env RAG chua co APP_API_KEY." }

New-Item -ItemType Directory -Force -Path (Join-Path $bff "data") | Out-Null
@(
    "CHATBOT_ENVIRONMENT=development"
    "CHATBOT_DATABASE_BACKEND=sqlite"
    "CHATBOT_DATABASE_PATH=data/chatbot.sqlite3"
    "CHATBOT_AUTH_DISABLED=true"
    "CHATBOT_PROVIDER=rag"
    "CHATBOT_RAG_BASE_URL=http://127.0.0.1:8000"
    "CHATBOT_RAG_API_KEY=$key"
    "CHATBOT_RAG_TIMEOUT_SECONDS=90"
) | Set-Content -LiteralPath (Join-Path $bff ".env") -Encoding utf8

$venv = Join-Path $bff ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv $venv
    & $py -m pip install -q -e (Join-Path $bff ".[test]")
}
& $py -m pip install -q httpx

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Cau noi http://127.0.0.1:30957  (FE se noi toi day)"
Set-Location $bff
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 30957
