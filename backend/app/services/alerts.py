import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.config import get_settings

settings = get_settings()


def send_email_alert(subject: str, body: str, recipients: Iterable[str]) -> tuple[bool, str]:
    recipient_list = [r.strip() for r in recipients if r and r.strip()]
    if not recipient_list:
        return False, 'No recipients configured'

    if not settings.smtp_host:
        return False, 'SMTP host not configured'

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = settings.smtp_from_email
    msg['To'] = ', '.join(recipient_list)
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        return True, 'sent'
    except Exception as exc:  # pragma: no cover - depends on SMTP server
        return False, str(exc)
