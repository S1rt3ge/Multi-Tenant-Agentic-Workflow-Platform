"""Tests for M9 Connector Runtime and Trigger System."""

import asyncio
import json
import uuid

from httpx import AsyncClient


async def _create_workflow(
    client: AsyncClient,
    headers: dict,
    definition: dict | None = None,
    name: str = "Connector WF",
) -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": name, "description": "Connector runtime test"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    workflow = resp.json()

    if definition is not None:
        update = await client.put(
            f"/api/v1/workflows/{workflow['id']}",
            json={"definition": definition},
            headers=headers,
        )
        assert update.status_code == 200, update.text
        workflow = update.json()

    return workflow


def _connector_definition(
    url: str = "https://example.com/",
    credential_id: str | None = None,
    headers: dict | None = None,
) -> dict:
    data = {
        "label": "HTTP Request",
        "connector_key": "http",
        "action_key": "request",
        "input": {
            "url": url,
            "method": "GET",
            "headers": headers or {"Accept": "application/json"},
        },
    }
    if credential_id is not None:
        data["credential_id"] = credential_id

    return {
        "nodes": [
            {
                "id": "http-1",
                "type": "connector",
                "position": {"x": 0, "y": 0},
                "data": data,
            }
        ],
        "edges": [],
    }


async def _viewer_headers(client: AsyncClient, owner_headers: dict) -> dict:
    email = f"connector-viewer-{uuid.uuid4()}@test.com"
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": email, "role": "viewer"},
        headers=owner_headers,
    )
    assert invite.status_code == 201, invite.text
    invited = invite.json()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": invited["temporary_password"]},
    )
    assert login.status_code == 200, login.text

    set_password = await client.post(
        "/api/v1/auth/set-password",
        json={"password": "viewersecure123"},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert set_password.status_code == 200, set_password.text
    return {"Authorization": f"Bearer {set_password.json()['access_token']}"}


async def _other_tenant_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"connector-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Connector Tenant",
            "tenant_name": "Other Connector Tenant",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_credential(client: AsyncClient, headers: dict, name: str = "Example API") -> dict:
    resp = await client.post(
        "/api/v1/connector-credentials",
        json={
            "connector_key": "http",
            "name": name,
            "auth_type": "api_key_header",
            "config": {
                "header_name": "Authorization",
                "header_value": "Bearer secret-token-123",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _wait_for_finished_execution(client: AsyncClient, headers: dict, execution_id: str) -> dict:
    execution = None
    for _ in range(20):
        resp = await client.get(f"/api/v1/executions/{execution_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        execution = resp.json()
        if execution["status"] in {"completed", "failed", "cancelled"}:
            return execution
        await asyncio.sleep(0.05)
    assert execution is not None
    return execution


class TestConnectorCatalog:
    async def test_list_connectors_includes_http_manifest(self, client, auth_headers):
        resp = await client.get("/api/v1/connectors", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        http_connector = next(item for item in data["items"] if item["key"] == "http")
        assert http_connector["name"] == "HTTP"
        assert any(action["key"] == "request" for action in http_connector["actions"])


class TestConnectorCredentials:
    async def test_create_credential_redacts_secret(self, client, auth_headers):
        credential = await _create_credential(client, auth_headers)

        serialized = json.dumps(credential)
        assert credential["connector_key"] == "http"
        assert credential["auth_type"] == "api_key_header"
        assert credential["config_preview"]["header_name"] == "Authorization"
        assert credential["config_preview"]["header_value"] != "Bearer secret-token-123"
        assert "secret-token-123" not in serialized
        assert "encrypted_config" not in credential
        assert "config" not in credential

    async def test_viewer_cannot_create_credential(self, client, auth_headers):
        viewer_headers = await _viewer_headers(client, auth_headers)

        resp = await client.post(
            "/api/v1/connector-credentials",
            json={
                "connector_key": "http",
                "name": "Viewer API",
                "auth_type": "api_key_header",
                "config": {
                    "header_name": "Authorization",
                    "header_value": "Bearer viewer-secret",
                },
            },
            headers=viewer_headers,
        )

        assert resp.status_code == 403

    async def test_cross_tenant_credential_hidden(self, client, auth_headers):
        credential = await _create_credential(client, auth_headers)
        other_headers = await _other_tenant_headers(client)

        listed = await client.get(
            "/api/v1/connector-credentials?connector_key=http",
            headers=other_headers,
        )
        assert listed.status_code == 200, listed.text
        assert credential["id"] not in [item["id"] for item in listed.json()["items"]]

        delete = await client.delete(
            f"/api/v1/connector-credentials/{credential['id']}",
            headers=other_headers,
        )
        assert delete.status_code == 404

    async def test_delete_credential_soft_deletes(self, client, auth_headers):
        credential = await _create_credential(client, auth_headers)

        delete = await client.delete(
            f"/api/v1/connector-credentials/{credential['id']}",
            headers=auth_headers,
        )
        assert delete.status_code == 204, delete.text

        listed = await client.get("/api/v1/connector-credentials", headers=auth_headers)
        assert listed.status_code == 200, listed.text
        assert credential["id"] not in [item["id"] for item in listed.json()["items"]]


class TestWorkflowTriggers:
    async def test_create_webhook_trigger_returns_public_url(self, client, auth_headers):
        workflow = await _create_workflow(client, auth_headers, _connector_definition())

        resp = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={"trigger_type": "webhook", "config": {"auth": "none"}},
            headers=auth_headers,
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["trigger_type"] == "webhook"
        assert data["public_id"]
        assert f"/api/v1/webhooks/{data['public_id']}" in data["webhook_url"]

    async def test_webhook_creates_pending_execution(self, client, auth_headers):
        workflow = await _create_workflow(client, auth_headers, _connector_definition())
        trigger = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={"trigger_type": "webhook", "config": {"auth": "none"}},
            headers=auth_headers,
        )
        assert trigger.status_code == 201, trigger.text

        resp = await client.post(
            f"/api/v1/webhooks/{trigger.json()['public_id']}",
            json={"lead_id": "lead-123"},
            headers={"X-Api-Key": "secret-webhook-header"},
        )

        assert resp.status_code == 202, resp.text
        execution_id = resp.json()["execution_id"]
        execution = await client.get(f"/api/v1/executions/{execution_id}", headers=auth_headers)
        assert execution.status_code == 200, execution.text
        assert execution.json()["status"] == "pending"
        assert execution.json()["input_data"]["trigger"]["type"] == "webhook"
        assert execution.json()["input_data"]["payload"]["lead_id"] == "lead-123"

    async def test_webhook_trigger_rate_limit_rejects_over_limit_without_execution(
        self, client, auth_headers
    ):
        workflow = await _create_workflow(client, auth_headers, _connector_definition())
        trigger = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={
                "trigger_type": "webhook",
                "config": {
                    "auth": "none",
                    "rate_limit": {
                        "enabled": True,
                        "max_events": 1,
                        "window_seconds": 60,
                    },
                },
            },
            headers=auth_headers,
        )
        assert trigger.status_code == 201, trigger.text

        first = await client.post(
            f"/api/v1/webhooks/{trigger.json()['public_id']}",
            json={"lead_id": "accepted"},
            headers={"X-Webhook-Secret": "secret-webhook-header"},
        )
        assert first.status_code == 202, first.text

        second = await client.post(
            f"/api/v1/webhooks/{trigger.json()['public_id']}",
            json={"lead_id": "rejected"},
            headers={"X-Webhook-Secret": "secret-webhook-header"},
        )

        assert second.status_code == 429, second.text
        serialized_error = json.dumps(second.json())
        assert "rate limit" in serialized_error.lower()
        assert "rejected" not in serialized_error
        assert "secret-webhook-header" not in serialized_error

        executions = await client.get(
            f"/api/v1/executions?workflow_id={workflow['id']}&page=1&per_page=20",
            headers=auth_headers,
        )
        assert executions.status_code == 200, executions.text
        webhook_execution_ids = [
            item["id"]
            for item in executions.json()["items"]
            if item["input_data"]["trigger"]["type"] == "webhook"
        ]
        assert webhook_execution_ids == [first.json()["execution_id"]]

    async def test_webhook_trigger_disabled_rate_limit_preserves_ingest_behavior(
        self, client, auth_headers
    ):
        workflow = await _create_workflow(client, auth_headers, _connector_definition())
        trigger = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={
                "trigger_type": "webhook",
                "config": {
                    "auth": "none",
                    "rate_limit": {
                        "enabled": False,
                        "max_events": 1,
                        "window_seconds": 60,
                    },
                },
            },
            headers=auth_headers,
        )
        assert trigger.status_code == 201, trigger.text

        first = await client.post(
            f"/api/v1/webhooks/{trigger.json()['public_id']}",
            json={"lead_id": "first"},
        )
        second = await client.post(
            f"/api/v1/webhooks/{trigger.json()['public_id']}",
            json={"lead_id": "second"},
        )

        assert first.status_code == 202, first.text
        assert second.status_code == 202, second.text

    async def test_webhook_unknown_public_id_returns_404(self, client):
        resp = await client.post(
            f"/api/v1/webhooks/{uuid.uuid4().hex}",
            json={"lead_id": "missing"},
        )

        assert resp.status_code == 404

    async def test_hmac_webhook_rejects_unsigned_and_accepts_signed(self, client, auth_headers):
        import hashlib
        import hmac as hmac_lib

        secret = "super-secret-webhook-key-1234567890"
        workflow = await _create_workflow(client, auth_headers, _connector_definition())
        trigger = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={
                "trigger_type": "webhook",
                "config": {"auth": {"type": "hmac", "secret": secret}},
            },
            headers=auth_headers,
        )
        assert trigger.status_code == 201, trigger.text
        public_id = trigger.json()["public_id"]

        body = b'{"lead_id":"signed"}'

        # Unsigned request is rejected before any execution is created.
        unsigned = await client.post(
            f"/api/v1/webhooks/{public_id}",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert unsigned.status_code == 401, unsigned.text

        # Wrong signature is rejected.
        bad = await client.post(
            f"/api/v1/webhooks/{public_id}",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature-256": "sha256=deadbeef"},
        )
        assert bad.status_code == 401, bad.text

        # Correct signature is accepted.
        digest = hmac_lib.new(secret.encode(), body, hashlib.sha256).hexdigest()
        good = await client.post(
            f"/api/v1/webhooks/{public_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": f"sha256={digest}",
            },
        )
        assert good.status_code == 202, good.text

    async def test_hmac_webhook_requires_strong_secret_at_creation(self, client, auth_headers):
        workflow = await _create_workflow(client, auth_headers, _connector_definition())
        resp = await client.post(
            f"/api/v1/workflows/{workflow['id']}/triggers",
            json={
                "trigger_type": "webhook",
                "config": {"auth": {"type": "hmac", "secret": "short"}},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422, resp.text


class TestConnectorRuntime:
    async def test_http_connector_blocks_private_network(self, client, auth_headers):
        workflow = await _create_workflow(
            client,
            auth_headers,
            _connector_definition(url="http://127.0.0.1:8000/internal"),
        )

        started = await client.post(
            f"/api/v1/workflows/{workflow['id']}/execute",
            json={"input_data": {"text": "block private network"}},
            headers=auth_headers,
        )
        assert started.status_code == 201, started.text

        execution = await _wait_for_finished_execution(
            client, auth_headers, started.json()["execution_id"]
        )
        assert execution["status"] == "failed"
        assert "private" in (execution["error_message"] or "").lower()

    async def test_http_connector_logs_sanitized_failure(self, client, auth_headers):
        workflow = await _create_workflow(
            client,
            auth_headers,
            _connector_definition(
                url="http://127.0.0.1:8000/internal",
                headers={"Authorization": "Bearer secret-token-123"},
            ),
        )

        started = await client.post(
            f"/api/v1/workflows/{workflow['id']}/execute",
            json={"input_data": {"text": "sanitize"}},
            headers=auth_headers,
        )
        assert started.status_code == 201, started.text
        await _wait_for_finished_execution(client, auth_headers, started.json()["execution_id"])

        logs = await client.get(
            f"/api/v1/executions/{started.json()['execution_id']}/logs",
            headers=auth_headers,
        )
        assert logs.status_code == 200, logs.text
        serialized_logs = json.dumps(logs.json())
        assert "secret-token-123" not in serialized_logs
        assert logs.json()[0]["node_type"] == "connector"
        assert logs.json()[0]["connector_key"] == "http"
        assert logs.json()[0]["sanitized_error"]

    async def test_workflow_doctor_detects_missing_connector_credential(
        self, client, auth_headers
    ):
        workflow = await _create_workflow(
            client,
            auth_headers,
            _connector_definition(credential_id=str(uuid.uuid4())),
        )

        started = await client.post(
            f"/api/v1/workflows/{workflow['id']}/execute",
            json={"input_data": {"text": "missing credential"}},
            headers=auth_headers,
        )
        assert started.status_code == 201, started.text
        execution = await _wait_for_finished_execution(
            client, auth_headers, started.json()["execution_id"]
        )
        assert execution["status"] == "failed"

        diagnose = await client.post(
            f"/api/v1/executions/{started.json()['execution_id']}/diagnose",
            json={},
            headers=auth_headers,
        )
        assert diagnose.status_code == 201, diagnose.text
        suggestion = diagnose.json()["items"][0]
        assert suggestion["detector_code"] == "missing_connector_credential"
        assert suggestion["severity"] == "high"
        assert suggestion["patch"]["operations"] == []
