param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "== containers =="
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml ps

Write-Host "== readiness =="
$readiness = $null
$lastReadinessError = $null
for ($attempt = 1; $attempt -le 15; $attempt++) {
    try {
        $readiness = Invoke-RestMethod "$BaseUrl/ready"
        break
    } catch {
        $lastReadinessError = $_.Exception.Message
        if ($attempt -eq 15) {
            throw "Readiness did not become available after 30 seconds: $lastReadinessError"
        }
        Write-Host "API ainda iniciando (tentativa $attempt/15); aguardando 2s..."
        Start-Sleep -Seconds 2
    }
}
$readiness | ConvertTo-Json -Depth 6

Write-Host "== metrics =="
Invoke-RestMethod "$BaseUrl/api/system/metrics" | ConvertTo-Json -Depth 6
