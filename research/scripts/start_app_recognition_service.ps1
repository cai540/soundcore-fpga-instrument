param([int]$Port=18765)
$ErrorActionPreference='Stop'
$projectDirectory=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDirectory=Join-Path $projectDirectory 'build/app_product_20261101'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$listener=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if($listener){
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener[0].OwningProcess)"
    if($process.CommandLine -notlike '*-m score_api*'){throw 'The requested port is occupied by another application.'}
    Write-Output "Recognition service is already running on loopback port $Port."
    exit 0
}
$python=Join-Path $projectDirectory '.venv_audio/Scripts/python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'The maintained recognition runtime is missing.'}
$service=Start-Process -FilePath $python -ArgumentList @('-u','-m','score_api','--host','127.0.0.1','--port',"$Port",'--config','config/score_api_bailian.json','--work-dir','.score-api/app-service','--app-sessions','--resident') -WorkingDirectory $projectDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'app-service.out.log') -RedirectStandardError (Join-Path $logDirectory 'app-service.err.log') -PassThru
Write-Output "Recognition service started. Process $($service.Id), loopback port $Port."
