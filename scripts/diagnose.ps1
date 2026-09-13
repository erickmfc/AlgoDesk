param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "== containers =="
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml ps

Write-Host "== readiness =="
Invoke-RestMethod "$BaseUrl/ready" | ConvertTo-Json -Depth 6

Write-Host "== metrics =="
Invoke-RestMethod "$BaseUrl/api/system/metrics" | ConvertTo-Json -Depth 6
