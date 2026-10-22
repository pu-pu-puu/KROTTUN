param([switch]$InspectOnly)
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\010726Admin\AppData\Local\Programs\Python\Python314\python.exe'
$project = 'D:\Projects\KROTTUN'
$helper = Join-Path $project 'tools\host-validation\proxy_failover.py'
$nonce = [Guid]::NewGuid().ToString()
$arguments = '"'+$helper+'" --run-nonce '+$nonce
if ($InspectOnly) { $arguments += ' --inspect-only' }
Write-Host 'Stage 3 uses saved EE then US in memory. Live mode changes WFP/TUN and kills only its test cores.'
Write-Host 'Watchdog recovery target 100 seconds; Windows/native API failures can delay recovery.'
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -Verb RunAs -WindowStyle Hidden -Wait -PassThru
Write-Host ('Exit code: '+$process.ExitCode)
Write-Host (Join-Path $project 'tools\host-validation\reports\stage3.json')
if ($process.ExitCode -ne 0) { throw 'Stage3 not passed. Inspect sanitized reports; verify network.' }
