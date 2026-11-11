$ErrorActionPreference = "Stop"
$dir = Join-Path $PSScriptRoot "lounge"
Set-Location $dir
Write-Host "Sanh phong http://127.0.0.1:5170"
python -m http.server 5170 --bind 127.0.0.1
