# EXPLICIT MANUAL RECOVERY ONLY. This removes owned WFP protection.
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\010726Admin\AppData\Local\Programs\Python\Python314\python.exe'
$project = 'D:\Projects\KROTTUN'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    # Visible console is intentional: recovery errors must remain readable offline.
    Start-Process 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Verb RunAs -ArgumentList '-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"') -Wait
    exit
}
Write-Host 'Close KROTTUN first. Removing KROTTUN owned protection explicitly.'
Write-Host 'Corrupt WFP metadata can prevent release. Success is not guaranteed; inspect output.'
Set-Location -LiteralPath $project
& $python -m core.kill_switch --release
if ($LASTEXITCODE -ne 0) { throw ('Recovery failed, exit ' + $LASTEXITCODE + '. Protection may remain; retain this error for manual diagnosis.') }
Write-Host 'Release command succeeded. Verify network separately.'
