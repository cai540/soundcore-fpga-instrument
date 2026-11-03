param(
    [Parameter(Mandatory=$true)][string]$Audio,
    [string]$Output,
    [double]$Start=0,
    [double]$Duration=0
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$researchRoot=Join-Path $projectRoot 'build/vocal_oss_20261029'
$sourceAudio=(Resolve-Path -LiteralPath $Audio).Path
if (-not $Output) { $Output=Join-Path $projectRoot ('output/register_candidate_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
$savedPath=$env:PYTHONPATH
$savedEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONPATH=(Join-Path $projectRoot 'build/vocal_pitch_grounded_20261029/extra')+';'+(Join-Path $projectRoot 'build/vocal_syllable_main_20261029/extra')+';'+(Join-Path $researchRoot 'extra')+';'+$PSScriptRoot
    & (Join-Path $researchRoot 'venv/Scripts/python.exe') -u (Join-Path $PSScriptRoot 'transcribe_register_candidate.py') $sourceAudio --output $Output --start $Start --duration $Duration
    if ($LASTEXITCODE -ne 0) { throw "Register candidate failed: $LASTEXITCODE" }
}
finally {
    $env:PYTHONPATH=$savedPath
    $env:PYTHONIOENCODING=$savedEncoding
}
