param([switch]$Lan,[int]$Port=8765,[switch]$CopyConnectionCode,[switch]$LocalAsr)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$cloudConfig = Join-Path $projectRoot 'config/score_api_bailian.json'
$configPath = if (!$LocalAsr -and (Test-Path -LiteralPath $cloudConfig)) {$cloudConfig} else {Join-Path $projectRoot 'config/score_api_models.json'}
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$servicePython = $config.python
if (!(Test-Path -LiteralPath $servicePython)) { throw "Missing model Python: $servicePython" }
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'ffmpeg is required on PATH' }
foreach ($model in $config.models.PSObject.Properties) {
    if ($model.Name -eq 'asr' -and $config.speech.provider -eq 'bailian') {continue}
    if (!(Test-Path -LiteralPath $model.Value)) { throw "Missing model: $($model.Name)" }
}
Write-Host "Speech observer: $($config.speech.provider) (local pitch/alignment models remain active)"
$keyFile = Join-Path $projectRoot '.score-api/service.key'
New-Item -ItemType Directory -Path (Split-Path -Parent $keyFile) -Force | Out-Null
if (!(Test-Path -LiteralPath $keyFile)) {
    & $servicePython -c "import secrets; from pathlib import Path; p=Path('.score-api/service.key'); p.open('x',encoding='utf8').write(secrets.token_urlsafe(32))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create service connection code' }
}
if ($CopyConnectionCode) {Set-Clipboard -Value (Get-Content -LiteralPath $keyFile -Raw).Trim(); Write-Host 'Connection code copied to clipboard.'}
$bindAddress = if ($Lan) {'0.0.0.0'} else {'127.0.0.1'}
if ($Lan) {
    Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)'} | ForEach-Object {
        Write-Host "Phone API address: http://$($_.IPAddress):$Port"
    }
} else {Write-Host "Local API address: http://127.0.0.1:$Port (use -Lan for a phone on Wi-Fi)"}
Write-Host "Connection code file: $keyFile"
Write-Host 'Keep this console running while recognizing. Press Ctrl+C to stop.'
$env:PYTHONIOENCODING = 'utf-8'
& $servicePython -u -m score_api --host $bindAddress --port $Port --config $configPath
exit $LASTEXITCODE
