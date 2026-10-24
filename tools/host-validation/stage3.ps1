param([switch]$InspectOnly,[switch]$AvailabilityOnly,[switch]$UiCheck,[ValidateSet('EE','US')][string]$PrimaryCountry = 'EE',[ValidateRange(1,1000)][int]$UsIndex = 1,[ValidateSet('Core','Proxy')][string]$FaultMode = 'Core')
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\010726Admin\AppData\Local\Programs\Python\Python314\python.exe'
$project = 'D:\Projects\KROTTUN'
$helper = Join-Path $project 'tools\host-validation\proxy_failover.py'
$nonce = [Guid]::NewGuid().ToString()
$arguments = '"'+$helper+'" --run-nonce '+$nonce+' --primary-country '+$PrimaryCountry+' --us-index '+$UsIndex+' --fault-mode '+$FaultMode
if ($InspectOnly -and $AvailabilityOnly) { throw 'Choose one inventory mode' }
if ($InspectOnly) { $arguments += ' --inspect-only' }
if ($AvailabilityOnly) { $arguments += ' --availability-only' }
if ($UiCheck) { $arguments += ' --ui-check' }
Write-Host ('Stage 3 changes WFP/TUN; test fault mode: '+$FaultMode+'. Saved proxies stay unchanged.')
Write-Host 'Watchdog recovery target 100 seconds; Windows/native API failures can delay recovery.'
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -Verb RunAs -WindowStyle Hidden -Wait -PassThru
Write-Host ('Exit code: '+$process.ExitCode)
Write-Host (Join-Path $project 'tools\host-validation\reports\stage3.json')
if ($process.ExitCode -ne 0) { throw 'Stage3 not passed. Inspect sanitized reports; verify network.' }
