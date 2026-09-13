param(
    [string]$OutputDirectory = "E:\AlgoDesk\data\backups"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputPath = Join-Path $OutputDirectory "algodesk-$stamp.sql"
$dump = docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml exec -T postgres pg_dump -U algodesk -d algodesk
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed; no backup was written"
}
$dump | Out-File -FilePath $outputPath -Encoding utf8
Write-Host "PostgreSQL backup written to $outputPath"
