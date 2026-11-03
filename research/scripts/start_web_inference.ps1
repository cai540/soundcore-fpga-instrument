param([switch]$Stop)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$stopFile=Join-Path $projectRoot '.score-api/web-worker.stop'
if($Stop){[IO.File]::WriteAllText($stopFile,'stop');Write-Host 'Inference worker will stop safely.';exit}
if(Test-Path -LiteralPath $stopFile){Remove-Item -LiteralPath $stopFile}
if(!(Test-Path -LiteralPath '.score-api/web-worker.json')){throw 'Missing private business worker credentials.'}
$config=Get-Content -LiteralPath 'config/score_api_bailian.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$logDir=Join-Path $projectRoot 'build/web_original_algorithm_20261030'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$taskProcess=Start-Process -FilePath $config.python -ArgumentList @('-u','-m','score_api.web_worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'agent.log') -RedirectStandardError (Join-Path $logDir 'agent.err.log') -PassThru
Write-Host "Business inference worker started (PID $($taskProcess.Id)); the computer must remain running."
