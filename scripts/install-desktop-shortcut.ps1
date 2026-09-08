$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'build-desktop-launcher.ps1') | Out-Null
$executable = Join-Path $projectRoot 'data\desktop-launcher\CreatorRadar.exe'
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutName = 'Creator Radar ' + [char]0x5DE5 + [char]0x4F5C + [char]0x53F0 + '.lnk'
$shortcutPath = Join-Path $desktopPath $shortcutName
$shortcutShell = New-Object -ComObject WScript.Shell
$shortcut = $shortcutShell.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -notin @($executable, (Join-Path $projectRoot 'Start-Workbench.cmd'))) {
    throw 'A different shortcut already uses this name; it was not overwritten.'
}
$shortcut.TargetPath = $executable
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = (Join-Path $projectRoot 'assets\creator-radar.ico') + ',0'
$shortcut.Description = 'Creator Radar - start local workspace'
$shortcut.WindowStyle = 1
$shortcut.Save()
$verified = $shortcutShell.CreateShortcut($shortcutPath)
if ($verified.TargetPath -ne $executable -or $verified.Arguments) { throw 'Shortcut verification failed.' }
Write-Output ('Desktop shortcut updated: ' + $shortcutPath)
