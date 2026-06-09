from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from processors.email_sender import (
    ResendSender,
    SMTPSender,
    create_email_sender,
)


class TestResendSender:
    def test_requires_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="RESEND_API_KEY"):
                ResendSender(api_key="")

    @patch.object(requests.Session, "post")
    def test_sends_email_successfully(self, mock_post: MagicMock) -> None:
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"id": "abc-123"}

        sender = ResendSender(api_key="re_123", from_address="test@ex.com")
        result = sender.send_email(
            recipient="user@ex.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )

        assert result["provider"] == "resend"
        assert result["message_id"] == "abc-123"
        mock_post.assert_called_once()

    @patch.object(requests.Session, "post")
    def test_retries_on_network_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.ConnectionError("timeout")

        sender = ResendSender(api_key="re_123", from_address="t@ex.com")
        with pytest.raises(requests.ConnectionError):
            sender.send_email("u@ex.com", "S", "<p>X</p>")

        assert mock_post.call_count == 3


class TestSMTPSender:
    def test_requires_credentials(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="SMTP_USERNAME"):
                SMTPSender(username="", password="")

    @patch("processors.email_sender.smtplib.SMTP")
    def test_sends_email_successfully(self, mock_smtp: MagicMock) -> None:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        sender = SMTPSender(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            from_address="noreply@ex.com",
        )
        result = sender.send_email(
            recipient="user@ex.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )

        assert result["provider"] == "smtp"
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "user@ex.com"
        assert msg["Subject"] == "Test"

    @patch("processors.email_sender.smtplib.SMTP")
    def test_retries_on_smtp_error(self, mock_smtp: MagicMock) -> None:
        mock_smtp.return_value.__enter__.return_value.send_message.side_effect = (
            ConnectionError("refused")
        )

        sender = SMTPSender(
            host="smtp.example.com",
            port=587,
            username="u",
            password="p",
            from_address="n@ex.com",
        )
        with pytest.raises(ConnectionError):
            sender.send_email("u@ex.com", "S", "<p>X</p>")

        assert mock_smtp.return_value.__enter__.return_value.send_message.call_count == 3


class TestCreateEmailSender:
    @patch.dict("os.environ", {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": "re_123"})
    def test_creates_resend_sender(self) -> None:
        sender = create_email_sender()
        assert isinstance(sender, ResendSender)

    @patch.dict(
        "os.environ",
        {
            "EMAIL_PROVIDER": "smtp",
            "SMTP_USERNAME": "u",
            "SMTP_PASSWORD": "p",
        },
    )
    def test_creates_smtp_sender(self) -> None:
        sender = create_email_sender()
        assert isinstance(sender, SMTPSender)

    def test_raises_for_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unknown email provider"):
            create_email_sender("nonexistent")
