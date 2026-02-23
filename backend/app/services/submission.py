from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.workflow import SubmissionResult


class SubmissionService:
    def send_email(self, to_email: str, pdf_path: Path, run_id: str) -> SubmissionResult:
        if not settings.smtp_enabled:
            return SubmissionResult(
                channel="email",
                success=False,
                details="SMTP disabled. Enable APP_SMTP_ENABLED to send emails.",
            )

        try:
            message = EmailMessage()
            message["Subject"] = f"Completed tax form ({run_id})"
            message["From"] = settings.smtp_from
            message["To"] = to_email
            message.set_content("Attached is the completed tax form.")
            message.add_attachment(
                pdf_path.read_bytes(),
                maintype="application",
                subtype="pdf",
                filename=pdf_path.name,
            )

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
            return SubmissionResult(channel="email", success=True, details=f"Sent to {to_email}")
        except Exception as exc:  # pragma: no cover - network dependent
            return SubmissionResult(channel="email", success=False, details=str(exc))

    def post_webhook(self, webhook_url: str, run_id: str, pdf_path: Path) -> SubmissionResult:
        if not settings.webhook_enabled:
            return SubmissionResult(
                channel="webhook",
                success=False,
                details="Webhook disabled. Enable APP_WEBHOOK_ENABLED to post callbacks.",
            )

        payload = {
            "run_id": run_id,
            "file_name": pdf_path.name,
            "message": "Completed form generated",
        }
        try:
            with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
                response = client.post(webhook_url, json=payload)
            if 200 <= response.status_code < 300:
                return SubmissionResult(channel="webhook", success=True, details=f"POST {response.status_code}")
            return SubmissionResult(channel="webhook", success=False, details=f"POST {response.status_code}")
        except Exception as exc:  # pragma: no cover - network dependent
            return SubmissionResult(channel="webhook", success=False, details=str(exc))


submission_service = SubmissionService()
