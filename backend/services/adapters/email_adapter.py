import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.adapters.base_adapter import ProviderStatus, AdapterResult


class EmailAdapter:
    """
    Real Email Service Adapter (SMTP / SendGrid / AWS SES).
    Dispatches emergency briefings, responder notifications, and incident reports.
    """

    def is_configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.EMAIL_FROM and settings.TEST_EMAIL_ADDRESS)

    def configuration_issues(self) -> List[str]:
        return [name for name, value in {
            "SMTP_HOST": settings.SMTP_HOST,
            "SMTP_USERNAME": settings.SMTP_USERNAME,
            "SMTP_PASSWORD": settings.SMTP_PASSWORD,
            "EMAIL_FROM": settings.EMAIL_FROM,
            "TEST_EMAIL_ADDRESS": settings.TEST_EMAIL_ADDRESS,
        }.items() if not value]

    def validate_connection(self) -> AdapterResult:
        """Authenticate with SMTP without sending a message."""
        if not self.is_configured():
            return AdapterResult(False, ProviderStatus.NOT_CONFIGURED, "SMTP Mail Service", "Email",
                                 details={"missing": self.configuration_issues()}, error="SMTP provider not configured")
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            return AdapterResult(True, ProviderStatus.ACCEPTED, f"SMTP ({settings.SMTP_HOST})", "Email")
        except Exception:
            return AdapterResult(False, ProviderStatus.FAILED, "SMTP Mail Service", "Email", error="SMTP authentication failed")

    def send_email(self, recipients: List[str], subject: str, body_text: str, body_html: Optional[str] = None) -> AdapterResult:
        provider_name = "SMTP Mail Service"

        if not self.is_configured():
            return AdapterResult(
                success=False,
                status=ProviderStatus.NOT_CONFIGURED,
                provider=provider_name,
                channel="Email",
                recipient_count=0,
                details={"reason": "SMTP host or credentials missing in .env"},
                error="Email SMTP provider not configured"
            )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = ", ".join(recipients)

            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, recipients, msg.as_string())

            msg_id = f"MSG-EML-{uuid.uuid4().hex[:10]}"
            return AdapterResult(
                success=True,
                status=ProviderStatus.ACCEPTED,
                provider=f"SMTP ({settings.SMTP_HOST})",
                channel="Email",
                message_id=msg_id,
                recipient_count=len(recipients),
                details={"from": settings.EMAIL_FROM, "subject": subject}
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="Email",
                recipient_count=0,
                error=f"SMTP dispatch error: {str(e)}"
            )


email_adapter = EmailAdapter()
