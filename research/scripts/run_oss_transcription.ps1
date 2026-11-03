param(
    [Parameter(Mandatory=$true)][string]$Audio,
    [string]$Output,
    [ValidateSet('small','medium')][string]$Size='medium'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$researchRoot=Join-Path $projectRoot 'build/vocal_oss_20261029'
$pythonPath=Join-Path $researchRoot 'venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing isolated research Python runtime.' }
$sourceAudio=(Resolve-Path -LiteralPath $Audio).Path
if (-not $Output) { $Output=Join-Path $projectRoot ('output/oss_recording_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
$oldPythonPath=$env:PYTHONPATH
$oldIoEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONPATH=(Join-Path $researchRoot 'extra')+';'+$PSScriptRoot
    & $pythonPath -u (Join-Path $PSScriptRoot 'transcribe_vocal_oss.py') $sourceAudio --output $Output --size $Size --boundary-threshold 0.2
    if ($LASTEXITCODE -ne 0) { throw "Transcription failed: $LASTEXITCODE" }
}
finally {
    $env:PYTHONPATH=$oldPythonPath
    $env:PYTHONIOENCODING=$oldIoEncoding
}
