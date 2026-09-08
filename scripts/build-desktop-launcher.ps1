$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $projectRoot 'data\desktop-launcher'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler)) { throw 'Windows .NET Framework compiler is unavailable.' }
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$executable = Join-Path $outputDirectory 'CreatorRadar.exe'
$icon = Join-Path $projectRoot 'assets\creator-radar.ico'
& $compiler /nologo /codepage:65001 /target:winexe "/out:$executable" "/win32icon:$icon" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $PSScriptRoot 'desktop-launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Desktop launcher compilation failed.' }
Write-Output $executable
