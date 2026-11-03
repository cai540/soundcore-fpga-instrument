param(
    [Parameter(Mandatory=$true)][string]$Audio,
    [string]$Output,
    [double]$Start=0,
    [double]$Duration=0
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$researchRoot=Join-Path $projectRoot 'build/vocal_oss_20261029'
$syllableRoot=Join-Path $projectRoot 'build/vocal_syllable_main_20261029'
$sourceAudio=(Resolve-Path -LiteralPath $Audio).Path
if (-not $Output) { $Output=Join-Path $projectRoot ('output/main_note_recording_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
$previousPythonPath=$env:PYTHONPATH
$previousIoEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONPATH=(Join-Path $syllableRoot 'extra')+';'+(Join-Path $researchRoot 'extra')+';'+$PSScriptRoot
    & (Join-Path $researchRoot 'venv/Scripts/python.exe') -u (Join-Path $PSScriptRoot 'transcribe_syllable_main.py') $sourceAudio --output $Output --start $Start --duration $Duration
    if ($LASTEXITCODE -ne 0) { throw "Transcription failed: $LASTEXITCODE" }
}
finally {
    $env:PYTHONPATH=$previousPythonPath
    $env:PYTHONIOENCODING=$previousIoEncoding
}
