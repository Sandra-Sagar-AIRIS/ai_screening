from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import Select, select
import sqlalchemy as sa
from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.candidate_management.models import (
    Candidate,
    CandidateInteraction,
    CommunicationChannel,
    CommunicationConnection,
    CommunicationMessage,
    CommunicationMessageDirection,
    CommunicationMessageEvent,
    CommunicationMessageStatus,
    CommunicationProvider,
    CommunicationReminder,
    CommunicationTemplate,
    InteractionType,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class CommunicationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._fernet = self._build_fernet()

    def _build_fernet(self) -> Fernet | None:
        key = os.getenv("COMM_TOKEN_ENCRYPTION_KEY", "").strip()
        if not key:
            return None
        try:
            return Fernet(key.encode("utf-8"))
        except Exception:
            return None

    def _encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        if self._fernet is None:
            return value
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        if self._fernet is None:
            return value
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None

    def _state_secret(self) -> str:
        return os.getenv("COMM_OAUTH_STATE_SECRET", self.settings.jwt_secret_key)

    def build_oauth_state(self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, provider: str) -> str:
        payload = {
            "org_id": str(org_id),
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "provider": provider,
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        sig = hashlib.sha256(f"{raw}.{self._state_secret()}".encode("utf-8")).hexdigest()
        return base64.urlsafe_b64encode(f"{raw}.{sig}".encode("utf-8")).decode("utf-8")

    def parse_oauth_state(self, token: str) -> dict[str, str]:
        try:
            decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            raw, sig = decoded.rsplit(".", 1)
            expected = hashlib.sha256(f"{raw}.{self._state_secret()}".encode("utf-8")).hexdigest()
            if sig != expected:
                raise ValueError("signature mismatch")
            payload = json.loads(raw)
            if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
                raise ValueError("expired")
            return payload
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    def build_authorization_url(self, *, provider: str, state: str) -> str:
        if provider == CommunicationProvider.GMAIL.value:
            params = {
                "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
                "response_type": "code",
                "scope": "openid email profile https://www.googleapis.com/auth/gmail.send",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
            return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        if provider == CommunicationProvider.OUTLOOK.value:
            tenant = os.getenv("MS_TENANT_ID", "common")
            params = {
                "client_id": os.getenv("MS_CLIENT_ID", ""),
                "redirect_uri": os.getenv("MS_REDIRECT_URI", ""),
                "response_type": "code",
                "scope": "openid profile offline_access Mail.Send User.Read",
                "state": state,
            }
            return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{urlencode(params)}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")

    def upsert_oauth_connection(
        self, *, code: str, state: str, provider_override: str | None = None
    ) -> CommunicationConnection:
        parsed = self.parse_oauth_state(state)
        provider = provider_override or parsed["provider"]
        token_payload, account_email, account_id = self._exchange_oauth_code(provider=provider, code=code)

        stmt: Select[tuple[CommunicationConnection]] = select(CommunicationConnection).where(
            CommunicationConnection.org_id == UUID(parsed["org_id"]),
            CommunicationConnection.workspace_id == UUID(parsed["workspace_id"]),
            CommunicationConnection.user_id == UUID(parsed["user_id"]),
            CommunicationConnection.provider == provider,
            CommunicationConnection.external_account_id == account_id,
        )
        existing = self.db.scalar(stmt)
        expires_at = None
        if token_payload.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_payload["expires_in"]))

        if existing is None:
            existing = CommunicationConnection(
                org_id=UUID(parsed["org_id"]),
                workspace_id=UUID(parsed["workspace_id"]),
                user_id=UUID(parsed["user_id"]),
                provider=CommunicationProvider(provider),
                channel=CommunicationChannel.EMAIL,
                external_account_id=account_id,
                external_account_email=account_email,
            )
        existing.access_token_encrypted = self._encrypt(token_payload.get("access_token"))
        existing.refresh_token_encrypted = self._encrypt(token_payload.get("refresh_token"))
        existing.token_expires_at = expires_at
        existing.status = "connected"
        existing.last_error = None
        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def list_connections(self, *, org_id: UUID, workspace_id: UUID, user_id: UUID) -> list[CommunicationConnection]:
        stmt = (
            select(CommunicationConnection)
            .where(
                CommunicationConnection.org_id == org_id,
                CommunicationConnection.workspace_id == workspace_id,
                CommunicationConnection.user_id == user_id,
            )
            .order_by(CommunicationConnection.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def disconnect(self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, provider: str) -> None:
        stmt = select(CommunicationConnection).where(
            CommunicationConnection.org_id == org_id,
            CommunicationConnection.workspace_id == workspace_id,
            CommunicationConnection.user_id == user_id,
            CommunicationConnection.provider == provider,
        )
        for conn in self.db.scalars(stmt):
            conn.status = "disconnected"
            conn.access_token_encrypted = None
            conn.refresh_token_encrypted = None
            self.db.add(conn)
        self.db.commit()

    def list_templates(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        channel: str = "email",
        search: str | None = None,
        category: str | None = None,
    ) -> list[CommunicationTemplate]:
        stmt = select(CommunicationTemplate).where(
            CommunicationTemplate.org_id == org_id,
            CommunicationTemplate.workspace_id == workspace_id,
            CommunicationTemplate.channel == channel,
            CommunicationTemplate.is_deleted.is_(False),
        )
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(
                sa.or_(
                    CommunicationTemplate.name.ilike(like),
                    CommunicationTemplate.subject_template.ilike(like),
                    CommunicationTemplate.body_template.ilike(like),
                )
            )
        if category:
            stmt = stmt.where(CommunicationTemplate.category == category)
        stmt = stmt.order_by(CommunicationTemplate.updated_at.desc())
        return list(self.db.scalars(stmt))

    def create_template(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        channel: str,
        provider: str | None,
        name: str,
        category: str | None,
        subject_template: str | None,
        body_template: str,
    ) -> CommunicationTemplate:
        tpl = CommunicationTemplate(
            org_id=org_id,
            workspace_id=workspace_id,
            channel=CommunicationChannel(channel),
            provider=CommunicationProvider(provider) if provider else None,
            name=name.strip(),
            category=category.strip() if category else None,
            subject_template=subject_template.strip() if subject_template else None,
            body_template=body_template,
            placeholders=self._extract_placeholders(subject_template, body_template),
            created_by=user_id,
            updated_by=user_id,
            is_deleted=False,
        )
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def update_template(
        self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, template_id: UUID, payload: dict[str, Any]
    ) -> CommunicationTemplate:
        tpl = self._require_template(org_id=org_id, workspace_id=workspace_id, template_id=template_id)
        for key in ("name", "subject_template", "body_template", "is_deleted"):
            if key in payload and payload[key] is not None:
                setattr(tpl, key, payload[key])
        if "category" in payload:
            tpl.category = payload["category"]
        tpl.updated_by = user_id
        tpl.placeholders = self._extract_placeholders(tpl.subject_template, tpl.body_template)
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def duplicate_template(
        self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, template_id: UUID
    ) -> CommunicationTemplate:
        tpl = self._require_template(org_id=org_id, workspace_id=workspace_id, template_id=template_id)
        copy = CommunicationTemplate(
            org_id=org_id,
            workspace_id=workspace_id,
            channel=tpl.channel,
            provider=tpl.provider,
            name=f"{tpl.name} Copy",
            category=tpl.category,
            subject_template=tpl.subject_template,
            body_template=tpl.body_template,
            placeholders=tpl.placeholders,
            created_by=user_id,
            updated_by=user_id,
            is_deleted=False,
        )
        self.db.add(copy)
        self.db.commit()
        self.db.refresh(copy)
        return copy

    def render_template(
        self, *, org_id: UUID, workspace_id: UUID, template_id: UUID, values: dict[str, Any]
    ) -> tuple[str | None, str, list[str]]:
        tpl = self._require_template(org_id=org_id, workspace_id=workspace_id, template_id=template_id)
        unresolved: list[str] = []

        def _sub(text: str | None) -> str | None:
            if text is None:
                return None

            def repl(match: re.Match[str]) -> str:
                key = match.group(1)
                if key not in values or values[key] is None:
                    unresolved.append(key)
                    return match.group(0)
                return str(values[key])

            return PLACEHOLDER_RE.sub(repl, text)

        subject = _sub(tpl.subject_template)
        body = _sub(tpl.body_template) or ""
        return subject, body, sorted(set(unresolved))

    def send_email(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        candidate_id: UUID,
        provider: str,
        to_email: str,
        subject: str | None,
        body: str | None,
        save_as_draft: bool,
        quick_action: str | None,
        attachments: list[dict[str, str]],
        template_id: UUID | None,
        template_values: dict[str, Any] | None,
        idempotency_key: str | None,
    ) -> CommunicationMessage:
        candidate = self.db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
                Candidate.deleted_at.is_(None),
            )
        )
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        if idempotency_key:
            existing = self.db.scalar(
                select(CommunicationMessage).where(
                    CommunicationMessage.org_id == org_id,
                    CommunicationMessage.workspace_id == workspace_id,
                    CommunicationMessage.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing

        rendered_subject = subject
        rendered_body = body
        if template_id:
            rendered_subject, rendered_body, unresolved = self.render_template(
                org_id=org_id,
                workspace_id=workspace_id,
                template_id=template_id,
                values=template_values or {},
            )
            if unresolved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "UNRESOLVED_TEMPLATE_PLACEHOLDERS", "placeholders": unresolved},
                )

        delivery_provider, connection = self._select_email_delivery(
            org_id=org_id, workspace_id=workspace_id, user_id=user_id, requested_provider=provider
        )
        record_provider = CommunicationProvider(delivery_provider) if connection is not None else CommunicationProvider(provider)
        from_address = connection.external_account_email if connection is not None else self.settings.smtp_from
        message = CommunicationMessage(
            org_id=org_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            channel=CommunicationChannel.EMAIL,
            provider=record_provider,
            direction=CommunicationMessageDirection.OUTBOUND,
            status=CommunicationMessageStatus.QUEUED,
            to_address=to_email,
            from_address=from_address,
            subject=rendered_subject,
            body=rendered_body,
            attachments=attachments or [],
            template_id=template_id,
            idempotency_key=idempotency_key,
            sent_by_user_id=user_id,
        )
        self.db.add(message)
        self.db.flush()
        self._append_message_event(
            message=message,
            event_type="queued" if not save_as_draft else "draft_saved",
            payload={"provider": delivery_provider, "to": to_email, "quick_action": quick_action},
        )

        if save_as_draft:
            message.status = CommunicationMessageStatus.DRAFT
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message

        try:
            if connection is not None:
                provider_message_id = self._send_via_provider(
                    provider=delivery_provider,
                    connection=connection,
                    channel="email",
                    to_email=to_email,
                    subject=rendered_subject or "",
                    body=rendered_body or "",
                    attachments=attachments or [],
                )
            else:
                provider_message_id = self._send_via_smtp(
                    to_email=to_email,
                    subject=rendered_subject or "",
                    body=rendered_body or "",
                    attachments=attachments or [],
                )
            message.provider_message_id = provider_message_id
            message.status = CommunicationMessageStatus.SENT
            self._append_message_event(
                message=message,
                event_type="sent",
                payload={"provider_message_id": provider_message_id},
            )
            self._append_candidate_interaction(
                org_id=org_id,
                workspace_id=workspace_id,
                candidate_id=candidate_id,
                user_id=user_id,
                title=f"Email sent via {delivery_provider}",
                body=(rendered_body or "")[:2000],
                metadata={
                    "channel": "email",
                    "provider": delivery_provider,
                    "to": to_email,
                    "subject": rendered_subject,
                    "message_id": str(message.id),
                    "provider_message_id": provider_message_id,
                },
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except HTTPException:
            raise
        except Exception as exc:
            if connection is not None and ("401" in str(exc) or "403" in str(exc) or "token" in str(exc).lower()):
                connection.status = "disconnected"
                connection.last_error = "Token expired or unauthorized. Reconnect required."
                self.db.add(connection)
            message.status = CommunicationMessageStatus.FAILED
            message.failure_reason = str(exc)
            self._append_message_event(
                message=message,
                event_type="failed",
                payload={"error": str(exc)},
            )
            self.db.add(message)
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email send failed.") from exc

    def send_whatsapp_message(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        candidate_id: UUID,
        to_phone: str,
        body: str,
        template_id: UUID | None,
        template_values: dict[str, Any] | None,
        idempotency_key: str | None,
        quick_action: str | None,
    ) -> CommunicationMessage:
        candidate = self.db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
                Candidate.deleted_at.is_(None),
            )
        )
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        rendered_body = body
        if template_id:
            _, rendered_body, unresolved = self.render_template(
                org_id=org_id,
                workspace_id=workspace_id,
                template_id=template_id,
                values=template_values or {},
            )
            if unresolved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "UNRESOLVED_TEMPLATE_PLACEHOLDERS", "placeholders": unresolved},
                )
        normalized_phone = self._normalize_whatsapp_phone(to_phone)
        rendered_body = (rendered_body or "").strip()
        if not rendered_body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp message cannot be empty.")
        from_number = self._normalize_twilio_whatsapp_from()
        message = CommunicationMessage(
            org_id=org_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            channel=CommunicationChannel.WHATSAPP,
            provider=CommunicationProvider.WHATSAPP,
            direction=CommunicationMessageDirection.OUTBOUND,
            status=CommunicationMessageStatus.QUEUED,
            to_address=normalized_phone,
            from_address=from_number,
            body=rendered_body,
            template_id=template_id,
            idempotency_key=idempotency_key,
            sent_by_user_id=user_id,
        )
        self.db.add(message)
        self.db.flush()
        self._append_message_event(message=message, event_type="queued", payload={"quick_action": quick_action})
        try:
            provider_message_id = self._send_via_twilio_whatsapp(
                to_phone=normalized_phone,
                from_phone=from_number,
                body=rendered_body,
            )
            message.provider_message_id = provider_message_id
            message.status = CommunicationMessageStatus.SENT
            self._append_message_event(message=message, event_type="sent", payload={"provider_message_id": provider_message_id})
            self._append_candidate_interaction(
                org_id=org_id,
                workspace_id=workspace_id,
                candidate_id=candidate_id,
                user_id=user_id,
                title="WhatsApp message sent",
                body=(rendered_body or "")[:2000],
                metadata={"channel": "whatsapp", "provider": "twilio", "to": normalized_phone, "message_id": str(message.id)},
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except HTTPException:
            raise
        except Exception as exc:
            message.status = CommunicationMessageStatus.FAILED
            message.failure_reason = self._friendly_twilio_error(exc)
            self._append_message_event(message=message, event_type="failed", payload={"error": message.failure_reason})
            self.db.add(message)
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message.failure_reason) from exc

    def list_messages(self, *, org_id: UUID, workspace_id: UUID, candidate_id: UUID, limit: int = 50) -> list[CommunicationMessage]:
        stmt = (
            select(CommunicationMessage)
            .where(
                CommunicationMessage.org_id == org_id,
                CommunicationMessage.workspace_id == workspace_id,
                CommunicationMessage.candidate_id == candidate_id,
            )
            .order_by(CommunicationMessage.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def seed_default_templates(self, *, org_id: UUID, workspace_id: UUID, user_id: UUID | None) -> None:
        existing = [
            *self.list_templates(org_id=org_id, workspace_id=workspace_id, channel=CommunicationChannel.EMAIL.value),
            *self.list_templates(org_id=org_id, workspace_id=workspace_id, channel=CommunicationChannel.WHATSAPP.value),
        ]
        names = {tpl.name.lower() for tpl in existing if not tpl.is_deleted}
        defaults = [
            (
                CommunicationChannel.EMAIL,
                "Interview Scheduled",
                "interview",
                "Interview Scheduled for {{job_title}} role",
                "Hi {{candidate_name}},\n\nYour interview is scheduled on {{interview_date}} at {{interview_time}}.\nMode: {{interview_mode}}.\n\nRegards,\nAIRIS Team",
            ),
            (
                CommunicationChannel.EMAIL,
                "Interview Reminder",
                "reminder",
                "Reminder: Upcoming interview for {{job_title}}",
                "Hi {{candidate_name}},\n\nReminder for your interview on {{interview_date}} at {{interview_time}}.\nPlease join via {{meeting_link}}.\n\nRegards,\nAIRIS Team",
            ),
            (
                CommunicationChannel.WHATSAPP,
                "WhatsApp Interview Reminder",
                "reminder",
                None,
                "Hi {{candidate_name}}, reminder for your interview on {{interview_date}} at {{interview_time}}.",
            ),
        ]
        for channel, name, category, subject, body in defaults:
            if name.lower() in names:
                continue
            self.db.add(
                CommunicationTemplate(
                    org_id=org_id,
                    workspace_id=workspace_id,
                    channel=channel,
                    provider=None,
                    name=name,
                    category=category,
                    subject_template=subject,
                    body_template=body,
                    placeholders=self._extract_placeholders(subject, body),
                    created_by=user_id,
                    updated_by=user_id,
                    is_deleted=False,
                )
            )
        self.db.commit()

    def create_reminder(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        candidate_id: UUID,
        channel: str,
        provider: str,
        to_address: str,
        subject: str | None,
        body: str | None,
        template_id: UUID | None,
        template_values: dict[str, Any],
        scheduled_for: datetime,
    ) -> CommunicationReminder:
        reminder = CommunicationReminder(
            org_id=org_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            channel=CommunicationChannel(channel),
            provider=CommunicationProvider(provider),
            to_address=to_address,
            subject=subject,
            body=body,
            template_id=template_id,
            template_values=template_values or {},
            scheduled_for=scheduled_for,
            status="pending",
            created_by_user_id=user_id,
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def list_reminders(self, *, org_id: UUID, workspace_id: UUID, candidate_id: UUID) -> list[CommunicationReminder]:
        stmt = (
            select(CommunicationReminder)
            .where(
                CommunicationReminder.org_id == org_id,
                CommunicationReminder.workspace_id == workspace_id,
                CommunicationReminder.candidate_id == candidate_id,
            )
            .order_by(CommunicationReminder.scheduled_for.desc())
        )
        return list(self.db.scalars(stmt))

    def process_due_reminders(self, *, org_id: UUID, workspace_id: UUID, user_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            select(CommunicationReminder)
            .where(
                CommunicationReminder.org_id == org_id,
                CommunicationReminder.workspace_id == workspace_id,
                CommunicationReminder.status == "pending",
                CommunicationReminder.scheduled_for <= now,
            )
            .order_by(CommunicationReminder.scheduled_for.asc())
            .limit(50)
        )
        due = list(self.db.scalars(stmt))
        processed = 0
        for reminder in due:
            try:
                template_id = reminder.template_id if not reminder.body else None
                if reminder.channel == CommunicationChannel.EMAIL:
                    self.send_email(
                        org_id=org_id,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        candidate_id=reminder.candidate_id,
                        provider=reminder.provider.value,
                        to_email=reminder.to_address or "",
                        subject=reminder.subject,
                        body=reminder.body,
                        save_as_draft=False,
                        quick_action="scheduled_reminder",
                        attachments=[],
                        template_id=template_id,
                        template_values=reminder.template_values or {},
                        idempotency_key=f"reminder-{reminder.id}",
                    )
                else:
                    self.send_whatsapp_message(
                        org_id=org_id,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        candidate_id=reminder.candidate_id,
                        to_phone=reminder.to_address or "",
                        body=reminder.body or "",
                        template_id=template_id,
                        template_values=reminder.template_values or {},
                        idempotency_key=f"reminder-{reminder.id}",
                        quick_action="scheduled_reminder",
                    )
                reminder.status = "sent"
                reminder.failure_reason = None
            except Exception as exc:
                reminder.status = "failed"
                reminder.failure_reason = str(exc)
            reminder.processed_at = datetime.now(timezone.utc)
            self.db.add(reminder)
            processed += 1
        self.db.commit()
        return processed

    def _exchange_oauth_code(self, *, provider: str, code: str) -> tuple[dict[str, Any], str | None, str]:
        if provider == CommunicationProvider.GMAIL.value:
            token_resp = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                    "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
                    "grant_type": "authorization_code",
                },
                timeout=20,
            )
            if token_resp.status_code >= 400:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth exchange failed.")
            payload = token_resp.json()
            account = httpx.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {payload.get('access_token', '')}"},
                timeout=20,
            ).json()
            email = account.get("email")
            account_id = account.get("id") or email or f"gmail-{hash(email)}"
            return payload, email, account_id
        if provider == CommunicationProvider.OUTLOOK.value:
            tenant = os.getenv("MS_TENANT_ID", "common")
            token_resp = httpx.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "code": code,
                    "client_id": os.getenv("MS_CLIENT_ID", ""),
                    "client_secret": os.getenv("MS_CLIENT_SECRET", ""),
                    "redirect_uri": os.getenv("MS_REDIRECT_URI", ""),
                    "grant_type": "authorization_code",
                },
                timeout=20,
            )
            if token_resp.status_code >= 400:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Outlook OAuth exchange failed.")
            payload = token_resp.json()
            me = httpx.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {payload.get('access_token', '')}"},
                timeout=20,
            ).json()
            email = me.get("mail") or me.get("userPrincipalName")
            account_id = me.get("id") or email or f"outlook-{hash(email)}"
            return payload, email, account_id
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")

    def _select_email_delivery(
        self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, requested_provider: str
    ) -> tuple[str, CommunicationConnection | None]:
        for provider in (CommunicationProvider.GMAIL.value, CommunicationProvider.OUTLOOK.value):
            conn = self.db.scalar(
                select(CommunicationConnection).where(
                    CommunicationConnection.org_id == org_id,
                    CommunicationConnection.workspace_id == workspace_id,
                    CommunicationConnection.user_id == user_id,
                    CommunicationConnection.provider == provider,
                    CommunicationConnection.status == "connected",
                )
            )
            if conn is not None:
                return provider, conn
        if requested_provider not in (CommunicationProvider.GMAIL.value, CommunicationProvider.OUTLOOK.value):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported email provider.")
        return "smtp", None

    def _send_via_smtp(self, *, to_email: str, subject: str, body: str, attachments: list[dict[str, str]]) -> str:
        if not self.settings.smtp_user or not self.settings.smtp_password or not self.settings.smtp_from:
            raise RuntimeError("SMTP is not configured.")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.settings.smtp_from
        msg["To"] = to_email
        msg.set_content(body)
        for attachment in attachments:
            content_b64 = attachment.get("content_base64", "")
            if not content_b64:
                continue
            content_type = attachment.get("content_type", "application/octet-stream")
            maintype, _, subtype = content_type.partition("/")
            msg.add_attachment(
                base64.b64decode(content_b64),
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.get("filename", "attachment"),
            )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(self.settings.smtp_user, self.settings.smtp_password)
            server.send_message(msg)
        return f"smtp-{datetime.now(timezone.utc).timestamp()}"

    def _normalize_whatsapp_phone(self, value: str) -> str:
        raw = (value or "").strip()
        if raw.startswith("whatsapp:"):
            raw = raw.removeprefix("whatsapp:").strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            digits = f"91{digits}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"whatsapp:+{digits}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid WhatsApp number with country code, for example +919347886094.",
        )

    def _normalize_twilio_whatsapp_from(self) -> str:
        number = (self.settings.twilio_whatsapp_number or "").strip()
        if not self.settings.twilio_account_sid or not self.settings.twilio_auth_token or not number:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp is not configured yet. Add Twilio sandbox credentials and try again.",
            )
        if number.startswith("whatsapp:+"):
            return number
        digits = re.sub(r"\D", "", number.removeprefix("whatsapp:"))
        if not digits:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp sender number is not configured correctly.",
            )
        return f"whatsapp:+{digits}"

    def _send_via_twilio_whatsapp(self, *, to_phone: str, from_phone: str, body: str) -> str:
        if not body.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp message cannot be empty.")
        client = TwilioClient(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        message = client.messages.create(from_=from_phone, to=to_phone, body=body)
        return message.sid

    def _friendly_twilio_error(self, exc: Exception) -> str:
        if isinstance(exc, TwilioRestException):
            if exc.status in (401, 403) or exc.code in (20003, 20404):
                return "WhatsApp provider authentication failed. Please verify Twilio credentials."
            if exc.code in (21211, 21614, 63031):
                return "Enter a valid WhatsApp number with country code."
            if exc.code in (63015, 63016):
                return "Candidate has not joined the Twilio WhatsApp sandbox yet."
            return "WhatsApp provider could not send this message. Please check sandbox setup and try again."
        return "WhatsApp send failed. Please check Twilio setup and try again."

    def _send_via_provider(
        self,
        *,
        provider: str,
        connection: CommunicationConnection,
        channel: str,
        to_email: str,
        subject: str,
        body: str,
        attachments: list[dict[str, str]],
    ) -> str:
        token = self._decrypt(connection.access_token_encrypted)
        if not token:
            raise RuntimeError("Provider connection is not authorized.")
        if provider == CommunicationProvider.GMAIL.value and channel == "email":
            boundary = "airis-boundary"
            parts = [
                f"From: {connection.external_account_email or ''}",
                f"To: {to_email}",
                f"Subject: {subject}",
                "MIME-Version: 1.0",
                f"Content-Type: multipart/mixed; boundary=\"{boundary}\"",
                "",
                f"--{boundary}",
                "Content-Type: text/plain; charset=utf-8",
                "",
                body,
            ]
            for attachment in attachments:
                filename = attachment.get("filename", "attachment")
                content_b64 = attachment.get("content_base64", "")
                content_type = attachment.get("content_type", "application/octet-stream")
                parts.extend(
                    [
                        f"--{boundary}",
                        f"Content-Type: {content_type}; name=\"{filename}\"",
                        "Content-Transfer-Encoding: base64",
                        f"Content-Disposition: attachment; filename=\"{filename}\"",
                        "",
                        content_b64,
                    ]
                )
            parts.extend([f"--{boundary}--", ""])
            mime = "\r\n".join(parts)
            raw = base64.urlsafe_b64encode(mime.encode("utf-8")).decode("utf-8")
            resp = httpx.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
                timeout=30,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Gmail send failed ({resp.status_code})")
            data = resp.json()
            return data.get("id") or data.get("threadId") or ""
        if provider == CommunicationProvider.OUTLOOK.value and channel == "email":
            graph_attachments: list[dict[str, Any]] = []
            for attachment in attachments:
                graph_attachments.append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": attachment.get("filename", "attachment"),
                        "contentType": attachment.get("content_type", "application/octet-stream"),
                        "contentBytes": attachment.get("content_base64", ""),
                    }
                )
            resp = httpx.post(
                "https://graph.microsoft.com/v1.0/me/sendMail",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": to_email}}],
                        "attachments": graph_attachments,
                    },
                    "saveToSentItems": True,
                },
                timeout=30,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Outlook send failed ({resp.status_code})")
            # sendMail endpoint does not always return message id.
            return f"outlook-{datetime.now(timezone.utc).timestamp()}"
        raise RuntimeError("Unsupported provider.")

    def _append_message_event(self, *, message: CommunicationMessage, event_type: str, payload: dict[str, Any]) -> None:
        self.db.add(
            CommunicationMessageEvent(
                org_id=message.org_id,
                workspace_id=message.workspace_id,
                message_id=message.id,
                event_type=event_type,
                provider_payload=payload,
            )
        )

    def _append_candidate_interaction(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        title: str,
        body: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self.db.add(
            CandidateInteraction(
                org_id=org_id,
                workspace_id=workspace_id,
                candidate_id=candidate_id,
                interaction_type=InteractionType.EMAIL,
                title=title,
                body=body,
                interaction_metadata=metadata,
                actor_user_id=user_id,
                actor_role="recruiter",
            )
        )

    def _extract_placeholders(self, subject: str | None, body: str) -> list[str]:
        keys = set(PLACEHOLDER_RE.findall(subject or ""))
        keys.update(PLACEHOLDER_RE.findall(body or ""))
        return sorted(keys)

    def _require_template(self, *, org_id: UUID, workspace_id: UUID, template_id: UUID) -> CommunicationTemplate:
        tpl = self.db.scalar(
            select(CommunicationTemplate).where(
                CommunicationTemplate.id == template_id,
                CommunicationTemplate.org_id == org_id,
                CommunicationTemplate.workspace_id == workspace_id,
                CommunicationTemplate.is_deleted.is_(False),
            )
        )
        if tpl is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
        return tpl

    def _require_connection(
        self, *, org_id: UUID, workspace_id: UUID, user_id: UUID, provider: str
    ) -> CommunicationConnection:
        conn = self.db.scalar(
            select(CommunicationConnection).where(
                CommunicationConnection.org_id == org_id,
                CommunicationConnection.workspace_id == workspace_id,
                CommunicationConnection.user_id == user_id,
                CommunicationConnection.provider == provider,
                CommunicationConnection.status == "connected",
            )
        )
        if conn is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider} is not connected.")
        return conn
