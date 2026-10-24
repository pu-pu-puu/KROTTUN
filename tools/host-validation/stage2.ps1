$ErrorActionPreference = 'Stop'
$python = 'C:\Users\010726Admin\AppData\Local\Programs\Python\Python314\python.exe'
$project = 'D:\Projects\KROTTUN'
$helper = Join-Path $project 'tools\host-validation\live_smoke.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Configured Python missing' }
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw 'Live smoke helper missing' }
Write-Host 'STAGE 2 LIVE: temporarily blocks direct internet for the whole PC. Close KROTTUN first.'
Write-Host 'Watchdog targets recovery at 20 seconds; Windows/native API failure can delay it. Inspect offline recovery instructions.'
$nonce = [Guid]::NewGuid().ToString()
$process = Start-Process -FilePath $python -ArgumentList ('"'+$helper+'" --run-nonce '+$nonce) -WorkingDirectory $project -Verb RunAs -WindowStyle Hidden -Wait -PassThru
Write-Host ('Exit code: '+$process.ExitCode)
Write-Host (Join-Path $project 'tools\host-validation\reports\stage2.json')
if ($process.ExitCode -ne 0) { throw 'Live smoke not passed; inspect reports and network state.' }
