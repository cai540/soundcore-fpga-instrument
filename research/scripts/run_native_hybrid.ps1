param(
    [Parameter(Mandatory=$true)][string]$Audio,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPython=Join-Path $taskRoot 'build/vocal_oss_20261029/venv/Scripts/python.exe'
if(-not (Test-Path -LiteralPath $taskPython)){throw 'Missing isolated vocal research Python'}
$taskInput=(Resolve-Path -LiteralPath $Audio).Path
$taskOutput=[System.IO.Path]::GetFullPath($Output)
$taskPreviousPythonPath=$env:PYTHONPATH
$taskPreviousEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONPATH=(Join-Path $taskRoot 'build/vocal_oss_20261029/extra')+';'+(Join-Path $taskRoot 'scripts')
    $env:PYTHONIOENCODING='utf-8'
    & $taskPython (Join-Path $taskRoot 'scripts/transcribe_native_hybrid.py') $taskInput --output $taskOutput
    if($LASTEXITCODE -ne 0){throw "Native vocal pipeline exited with $LASTEXITCODE"}
} finally {
    $env:PYTHONPATH=$taskPreviousPythonPath
    $env:PYTHONIOENCODING=$taskPreviousEncoding
}
