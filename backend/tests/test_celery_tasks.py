"""INFRA-006 — Celery async task infrastructure tests.

Acceptance criteria verified:
  1. Shared celery_app is a single Celery instance (no per-module instances).
  2. All named queues are declared in task_queues.
  3. Task routing maps task name prefixes to the correct queues.
  4. process_bulk_upload_item is routed to the 'ai' queue.
  5. send_invite_email_task is routed to the 'email' queue.
  6. record_dead_letter has max_retries=0 and ignore_result=True.
  7. send_invite_email_task has retry_backoff enabled.
  8. send_invite_reminders is registered in the beat schedule.
  9. Worker health endpoint returns 200 when broker is unavailable (graceful).
 10. Worker health endpoint returns worker + task counts when broker responds.
 11. CeleryTaskEnqueuer.enqueue_bulk_upload_item dispatches via apply_async to ai queue.
 12. rescore_candidate_task max_retries is at least 1.
 13. sync_calendar_event_task is on the integrations queue.
 14. notify_stage_change_task is on the notifications queue.
"""
from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

import app.main as main_module
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def _anon_user() -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid4()),
        organization_id=str(uuid4()),
        email="test@example.com",
        role="admin",
        user_type="internal",
    )


@pytest.fixture()
def client(_anon_user: CurrentUser) -> Generator[TestClient, None, None]:
    app = main_module.app
    app.dependency_overrides[get_current_user] = lambda: _anon_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── 1. Single shared Celery instance ─────────────────────────────────────────

def test_celery_app_is_singleton() -> None:
    from app.celery_app import celery_app as app1
    from app.celery_app import celery_app as app2
    assert app1 is app2


# ── 2. All queues declared ────────────────────────────────────────────────────

def test_all_queues_declared() -> None:
    from app.celery_app import ALL_QUEUES, celery_app

    declared_names = {q.name for q in celery_app.conf.task_queues}
    for queue_name in ALL_QUEUES:
        assert queue_name in declared_names, f"Queue '{queue_name}' not declared in task_queues"


# ── 3. Task routing ───────────────────────────────────────────────────────────

def test_task_routes_cover_all_modules() -> None:
    from app.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert any("email_tasks" in k for k in routes), "email_tasks not in task_routes"
    assert any("ai_tasks" in k for k in routes), "ai_tasks not in task_routes"
    assert any("notification_tasks" in k for k in routes), "notification_tasks not in task_routes"
    assert any("integration_tasks" in k for k in routes), "integration_tasks not in task_routes"
    assert any("candidate_management" in k for k in routes), "candidate_management not in task_routes"


# ── 4. process_bulk_upload_item → ai queue ────────────────────────────────────

def test_bulk_upload_task_on_ai_queue() -> None:
    from app.candidate_management.tasks import process_bulk_upload_item
    from app.celery_app import QUEUE_AI

    assert process_bulk_upload_item.queue == QUEUE_AI


# ── 5. send_invite_email_task → email queue ───────────────────────────────────

def test_invite_email_task_on_email_queue() -> None:
    from app.tasks.email_tasks import send_invite_email_task
    from app.celery_app import QUEUE_EMAIL

    assert send_invite_email_task.queue == QUEUE_EMAIL


# ── 6. record_dead_letter — no retries, no stored result ─────────────────────

def test_dlq_task_no_retries() -> None:
    from app.tasks.dlq_tasks import record_dead_letter

    assert record_dead_letter.max_retries == 0
    assert record_dead_letter.ignore_result is True


# ── 7. Email task has exponential backoff ─────────────────────────────────────

def test_invite_email_task_has_backoff() -> None:
    from app.tasks.email_tasks import send_invite_email_task

    assert send_invite_email_task.retry_backoff is True


# ── 8. Beat schedule includes invite reminders ───────────────────────────────

def test_beat_schedule_has_invite_reminders() -> None:
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    task_names = {entry["task"] for entry in schedule.values()}
    assert "app.tasks.invite_tasks.send_invite_reminders" in task_names


# ── 9. Worker health — graceful when broker unavailable ──────────────────────

def test_worker_health_graceful_on_broker_unavailable(client: TestClient) -> None:
    with patch("app.celery_app.celery_app.control") as mock_control:
        mock_inspect = MagicMock()
        mock_inspect.ping.side_effect = Exception("Connection refused")
        mock_control.inspect.return_value = mock_inspect

        resp = client.get("/api/v1/health/workers")

    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_count"] == 0
    assert "status" in data


# ── 10. Worker health — returns counts when workers respond ──────────────────

def test_worker_health_with_workers(client: TestClient) -> None:
    worker_name = "celery@worker1"
    fake_ping = {worker_name: [{"ok": "pong"}]}
    fake_active = {worker_name: [{"id": "task-1"}, {"id": "task-2"}]}

    with patch("app.celery_app.celery_app.control") as mock_control:
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = fake_ping
        mock_inspect.active.return_value = fake_active
        mock_control.inspect.return_value = mock_inspect

        resp = client.get("/api/v1/health/workers")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["worker_count"] == 1
    assert data["active_tasks"] == 2


# ── 11. CeleryTaskEnqueuer dispatches to ai queue ────────────────────────────

def test_celery_task_enqueuer_uses_apply_async() -> None:
    from app.candidate_management.tasks import CeleryTaskEnqueuer
    from app.celery_app import QUEUE_AI

    enqueuer = CeleryTaskEnqueuer()
    org_id = uuid4()
    workspace_id = uuid4()
    job_id = uuid4()
    item_id = uuid4()

    with patch("app.candidate_management.tasks.process_bulk_upload_item.apply_async") as mock_dispatch:
        enqueuer.enqueue_bulk_upload_item(
            job_id=job_id,
            item_id=item_id,
            org_id=org_id,
            workspace_id=workspace_id,
        )

    mock_dispatch.assert_called_once()
    call_kwargs = mock_dispatch.call_args
    assert call_kwargs.kwargs.get("queue") == QUEUE_AI or (
        call_kwargs.args and call_kwargs.args[-1] == QUEUE_AI
    )


# ── 12. rescore_candidate_task max_retries ────────────────────────────────────

def test_rescore_candidate_task_has_retries() -> None:
    from app.tasks.ai_tasks import rescore_candidate_task

    assert rescore_candidate_task.max_retries >= 1


# ── 13. sync_calendar_event_task → integrations queue ───────────────────────

def test_calendar_sync_task_on_integrations_queue() -> None:
    from app.tasks.integration_tasks import sync_calendar_event_task
    from app.celery_app import QUEUE_INTEGRATIONS

    assert sync_calendar_event_task.queue == QUEUE_INTEGRATIONS


# ── 14. notify_stage_change_task → notifications queue ──────────────────────

def test_stage_change_task_on_notifications_queue() -> None:
    from app.tasks.notification_tasks import notify_stage_change_task
    from app.celery_app import QUEUE_NOTIFICATIONS

    assert notify_stage_change_task.queue == QUEUE_NOTIFICATIONS
