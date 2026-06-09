from __future__ import annotations

import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, ClassVar

import requests

logger = logging.getLogger(__name__)

_RETRY_MAX: int = 3
_RETRY_BASE_DELAY: float = 1.0


def _retry(max_attempts: int = _RETRY_MAX, base_delay: float = _RETRY_BASE_DELAY):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, smtplib.SMTPException, ConnectionError) as exc:
                    last_exc = exc
                    logger.warning(
                        "%s attempt %d/%d failed: %s",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    if attempt < max_attempts:
                        time.sleep(base_delay * (2 ** (attempt - 1)))
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


class EmailSender(ABC):
    @abstractmethod
    def send_email(self, recipient: str, subject: str, html_content: str) -> dict[str, Any]:
        """Send an HTML email. Returns a dict with delivery metadata."""
        ...


class ResendSender(EmailSender):
    API_BASE: ClassVar[str] = "https://api.resend.com"

    def __init__(self, api_key: str | None = None, from_address: str | None = None) -> None:
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        if not self.api_key:
            raise ValueError("RESEND_API_KEY is required for ResendSender")
        self.from_address = (
            from_address
            or os.getenv("EMAIL_FROM", "")
            or "Morning News <newsletter@yourdomain.com>"
        )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    @_retry()
    def send_email(self, recipient: str, subject: str, html_content: str) -> dict[str, Any]:
        payload: dict[str, str] = {
            "from": self.from_address,
            "to": recipient,
            "subject": subject,
            "html": html_content,
        }

        resp = self._session.post(
            f"{self.API_BASE}/emails",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Email sent via Resend: id=%s to=%s", data.get("id"), recipient)
        return {"provider": "resend", "message_id": data.get("id", ""), "recipient": recipient}


class SMTPSender(EmailSender):
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_address: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self.host = host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.from_address = (
            from_address
            or os.getenv("EMAIL_FROM", "")
            or "Morning News <newsletter@yourdomain.com>"
        )
        self.use_tls = use_tls

        if not self.username or not self.password:
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD are required for SMTPSender")

    @_retry()
    def send_email(self, recipient: str, subject: str, html_content: str) -> dict[str, Any]:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_address
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(self.host, self.port, timeout=30) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)

        logger.info("Email sent via SMTP to=%s", recipient)
        return {
            "provider": "smtp",
            "host": self.host,
            "recipient": recipient,
        }


_SENDER_MAP: dict[str, type[EmailSender]] = {
    "resend": ResendSender,
    "smtp": SMTPSender,
}


def create_email_sender(name: str | None = None) -> EmailSender:
    name = (name or os.getenv("EMAIL_PROVIDER", "smtp")).strip().lower()
    sender_cls = _SENDER_MAP.get(name)
    if not sender_cls:
        available = ", ".join(_SENDER_MAP)
        raise ValueError(f"Unknown email provider '{name}'. Available: {available}")
    return sender_cls()
