$ErrorActionPreference = "Stop"

docker compose up -d db backend

try {
    for ($i = 0; $i -lt 30; $i++) {
        try {
            Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get | Out-Null
            break
        }
        catch {
            Start-Sleep -Seconds 2
        }

        if ($i -eq 29) {
            throw "Backend health check did not become ready in time."
        }
    }

    $registerBody = @{
        email = "smoke@test.com"
        password = "securepass123"
        full_name = "Smoke User"
        tenant_name = "Smoke Corp"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" -Method Post -ContentType "application/json" -Body $registerBody | Out-Null

    $loginBody = @{
        email = "smoke@test.com"
        password = "securepass123"
    } | ConvertTo-Json

    $login = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
    $headers = @{ Authorization = "Bearer $($login.access_token)" }

    $me = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/me" -Method Get -Headers $headers
    if ($me.email -ne "smoke@test.com") {
        throw "Smoke check failed: unexpected /me response email."
    }

    Write-Output "Backend smoke check passed."
}
finally {
    docker compose down -v
}
