"""Tests for M12 dispatch incident analytics trends and SLA reporting."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.dispatch_alert import DispatchIncidentAcknowledgement


async def _create_incident_row(
    db_session,
    tenant_id: uuid.UUID,
    *,
    status: str,
    severity: str,
    created_at: datetime,
    resolved_at: datetime | None = None,
) -> DispatchIncidentAcknowledgement:
    row = DispatchIncidentAcknowledgement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key=f"dispatch:{uuid.uuid4().hex}",
        status=status,
        severity=severity,
        summary="Dispatch incident handoff required",
        alert_codes=["dead_lettered"],
        acknowledged_by_email="owner@test.com",
        acknowledged_by_name="Secret Owner",
        note="operator note token=secret-note-token",
        resolved_by_email="resolver@test.com" if resolved_at else None,
        resolved_by_name="Secret Resolver" if resolved_at else None,
        resolution_note="fixed token=secret-resolution-token" if resolved_at else None,
        resolved_at=resolved_at,
        created_at=created_at,
        updated_at=resolved_at or created_at,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_dispatch_incident_analytics_reports_trends_and_sla_without_secrets(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    now = datetime.now(timezone.utc)
    critical_created = now - timedelta(minutes=120)
    critical_resolved = now - timedelta(minutes=30)
    warning_created = now - timedelta(days=1, minutes=30)
    warning_resolved = warning_created + timedelta(minutes=20)
    open_created = now - timedelta(minutes=90)

    await _create_incident_row(
        db_session,
        tenant_id,
        status="resolved",
        severity="critical",
        created_at=critical_created,
        resolved_at=critical_resolved,
    )
    await _create_incident_row(
        db_session,
        tenant_id,
        status="resolved",
        severity="warning",
        created_at=warning_created,
        resolved_at=warning_resolved,
    )
    await _create_incident_row(
        db_session,
        tenant_id,
        status="acknowledged",
        severity="warning",
        created_at=open_created,
    )

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"incident-analytics-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Incident Analytics User",
            "tenant_name": "Other Incident Analytics Tenant",
        },
    )
    assert other.status_code == 201, other.text
    await _create_incident_row(
        db_session,
        uuid.UUID(other.json()["tenant_id"]),
        status="resolved",
        severity="critical",
        created_at=now - timedelta(minutes=240),
        resolved_at=now - timedelta(minutes=30),
    )

    resp = await client.get(
        "/api/v1/analytics/dispatch-incident-analytics?days=7&sla_minutes=60",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["window_days"] == 7
    assert data["sla_minutes"] == 60
    assert data["total_incidents"] == 3
    assert data["resolved_incidents"] == 2
    assert data["open_incidents"] == 1
    assert data["sla_breaches"] == 2
    assert data["sla_breach_rate"] == pytest.approx(66.7, abs=0.1)
    assert data["avg_resolution_minutes"] == pytest.approx(55.0, abs=0.1)

    assert len(data["trends"]) == 7
    trend_by_day = {item["day"]: item for item in data["trends"]}
    today = trend_by_day[now.strftime("%Y-%m-%d")]
    assert today["acknowledged"] == 2
    assert today["resolved"] == 1
    assert today["open"] == 1
    assert today["sla_breaches"] == 2
    warning_day = trend_by_day[warning_created.strftime("%Y-%m-%d")]
    assert warning_day["acknowledged"] == 1
    assert warning_day["resolved"] == 1
    assert warning_day["sla_breaches"] == 0

    severity = {item["severity"]: item for item in data["by_severity"]}
    assert severity["critical"]["total_incidents"] == 1
    assert severity["critical"]["resolved_incidents"] == 1
    assert severity["critical"]["sla_breaches"] == 1
    assert severity["critical"]["avg_resolution_minutes"] == pytest.approx(90.0, abs=0.1)
    assert severity["warning"]["total_incidents"] == 2
    assert severity["warning"]["resolved_incidents"] == 1
    assert severity["warning"]["open_incidents"] == 1
    assert severity["warning"]["sla_breaches"] == 1
    assert severity["warning"]["avg_resolution_minutes"] == pytest.approx(20.0, abs=0.1)

    serialized = str(data)
    assert "secret-note-token" not in serialized
    assert "secret-resolution-token" not in serialized
    assert "owner@test.com" not in serialized
    assert "resolver@test.com" not in serialized


@pytest.mark.asyncio
async def test_dispatch_incident_analytics_validates_query_and_auth(
    client,
    auth_headers,
):
    no_auth = await client.get("/api/v1/analytics/dispatch-incident-analytics")
    assert no_auth.status_code == 401

    invalid_days = await client.get(
        "/api/v1/analytics/dispatch-incident-analytics?days=0",
        headers=auth_headers,
    )
    assert invalid_days.status_code == 422

    invalid_sla = await client.get(
        "/api/v1/analytics/dispatch-incident-analytics?sla_minutes=0",
        headers=auth_headers,
    )
    assert invalid_sla.status_code == 422
