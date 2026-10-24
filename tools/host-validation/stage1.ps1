$ErrorActionPreference = 'Stop'
$python = 'C:\Users\010726Admin\AppData\Local\Programs\Python\Python314\python.exe'
$project = 'D:\Projects\KROTTUN'
$helper = Join-Path $project 'tools\host-validation\preflight.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Configured Python missing' }
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw 'Preflight helper missing' }
$arguments = '"' + $helper + '"'
Write-Host 'Stage 1: native WFP transaction probe, always aborted. No protection will be applied.'
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -Verb RunAs -WindowStyle Hidden -PassThru -Wait
Write-Host ('Exit code: ' + $process.ExitCode)
Write-Host (Join-Path $project 'tools\host-validation\reports\stage1.txt')
if ($process.ExitCode -ne 0) { throw 'Preflight failed. Read reports; do not apply protection.' }
