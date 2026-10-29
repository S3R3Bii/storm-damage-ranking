param([Parameter(Mandatory=$true)][string]$SourceUrl,[Parameter(Mandatory=$true)][string]$TargetFile)
$ErrorActionPreference='Stop'
Invoke-WebRequest -UseBasicParsing -Uri $SourceUrl -OutFile $TargetFile -TimeoutSec 180
