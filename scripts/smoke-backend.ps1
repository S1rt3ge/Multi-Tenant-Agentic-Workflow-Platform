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

    $workflowBody = @{
        name = "Smoke Workflow"
        description = "Local smoke workflow"
        execution_pattern = "linear"
    } | ConvertTo-Json

    $workflow = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/" -Method Post -ContentType "application/json" -Headers $headers -Body $workflowBody
    if ($workflow.name -ne "Smoke Workflow") {
        throw "Smoke check failed: workflow was not created correctly."
    }

    $workflowList = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/" -Method Get -Headers $headers
    if (-not ($workflowList.items | Where-Object { $_.id -eq $workflow.id })) {
        throw "Smoke check failed: workflow not present in workflow list."
    }

    $workflowDetail = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/$($workflow.id)" -Method Get -Headers $headers
    if ($workflowDetail.id -ne $workflow.id) {
        throw "Smoke check failed: workflow detail lookup returned unexpected result."
    }

    Invoke-WebRequest -Uri "http://localhost:8000/api/v1/workflows/$($workflow.id)" -Method Delete -Headers $headers | Out-Null

    $toolBody = @{
        name = "Smoke API Tool"
        description = "Local smoke tool"
        tool_type = "api"
        config = @{
            url = "https://api.example.com/data"
            method = "GET"
            headers = @{
                Authorization = "Bearer secret-token-123"
            }
        }
    } | ConvertTo-Json -Depth 5

    $tool = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/tools/" -Method Post -ContentType "application/json" -Headers $headers -Body $toolBody
    if ($tool.name -ne "Smoke API Tool") {
        throw "Smoke check failed: tool was not created correctly."
    }

    $toolList = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/tools/" -Method Get -Headers $headers
    if (-not ($toolList | Where-Object { $_.id -eq $tool.id })) {
        throw "Smoke check failed: tool not present in tool list."
    }

    $toolUpdateBody = @{
        description = "Updated local smoke tool"
    } | ConvertTo-Json

    $updatedTool = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/tools/$($tool.id)" -Method Put -ContentType "application/json" -Headers $headers -Body $toolUpdateBody
    if ($updatedTool.description -ne "Updated local smoke tool") {
        throw "Smoke check failed: tool update did not persist."
    }

    Invoke-WebRequest -Uri "http://localhost:8000/api/v1/tools/$($tool.id)" -Method Delete -Headers $headers | Out-Null

    $executionWorkflowBody = @{
        name = "Execution Smoke Workflow"
        description = "Local execution smoke workflow"
        execution_pattern = "linear"
    } | ConvertTo-Json

    $executionWorkflow = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/" -Method Post -ContentType "application/json" -Headers $headers -Body $executionWorkflowBody

    $executionWorkflowUpdateBody = @{
        definition = @{
            nodes = @(
                @{
                    id = "node-1"
                    type = "agentNode"
                    position = @{ x = 0; y = 0 }
                    data = @{ label = "Smoke Agent" }
                }
            )
            edges = @()
        }
    } | ConvertTo-Json -Depth 6

    $executionWorkflow = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/$($executionWorkflow.id)" -Method Put -ContentType "application/json" -Headers $headers -Body $executionWorkflowUpdateBody

    $executionBody = @{
        input_data = @{ text = "smoke execution" }
    } | ConvertTo-Json -Depth 4

    $executionStart = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/$($executionWorkflow.id)/execute" -Method Post -ContentType "application/json" -Headers $headers -Body $executionBody
    if ($executionStart.status -ne "pending") {
        throw "Smoke check failed: execution did not start in pending state."
    }

    $executionList = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/executions" -Method Get -Headers $headers
    if (-not ($executionList.items | Where-Object { $_.id -eq $executionStart.execution_id })) {
        throw "Smoke check failed: execution not present in execution list."
    }

    $executionDetail = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/executions/$($executionStart.execution_id)" -Method Get -Headers $headers
    if ($executionDetail.id -ne $executionStart.execution_id) {
        throw "Smoke check failed: execution detail lookup returned unexpected result."
    }

    $executionLogs = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/executions/$($executionStart.execution_id)/logs" -Method Get -Headers $headers
    if ($null -eq $executionLogs) {
        throw "Smoke check failed: execution logs endpoint returned null."
    }

    $cancelledExecution = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/executions/$($executionStart.execution_id)/cancel" -Method Post -Headers $headers
    if ($cancelledExecution.status -ne "cancelled") {
        throw "Smoke check failed: execution was not cancelled correctly."
    }

    Write-Output "Backend auth + workflow + tool + execution smoke check passed."
}
finally {
    docker compose down -v
}
