param([Parameter(Mandatory=$true)][string]$Audio,
      [Parameter(Mandatory=$true)][string]$Output,
      [double]$Start=0,[double]$Duration=0)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH=(Join-Path $taskRoot 'build/vocal_oss_20261029/extra')+';'+$PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
& (Join-Path $taskRoot 'build/vocal_oss_20261029/venv/Scripts/python.exe') -u (Join-Path $PSScriptRoot 'transcribe_event_candidate.py') $Audio --output $Output --start $Start --duration $Duration
if($LASTEXITCODE -ne 0){throw "Event transcription failed: $LASTEXITCODE"}
