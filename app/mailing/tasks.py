from flask import current_app
from flask_mail import Message

from app.extensions import celery, db, mail
from app.mailing.models import EmailLog


def _log(recipient, template_name, status, provider_message_id, error_message):
    db.session.add(
        EmailLog(
            recipient=recipient,
            template_name=template_name,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
        )
    )
    db.session.commit()


@celery.task(bind=True, name="mailing.send_email", max_retries=3, default_retry_delay=30)
def send_email_task(self, recipient, subject, html_body, text_body, template_name):
    """Performs the actual SMTP send, with retry/backoff on transient
    failures (§5) — the thing the request itself must never wait on.
    EmailLog records the outcome either way; never the message content
    itself (e.g. a temp password), only metadata about the attempt.
    """
    message = Message(
        subject=subject,
        recipients=[recipient],
        body=text_body,
        html=html_body,
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    try:
        mail.send(message)
    except Exception as exc:
        _log(recipient, template_name, "failed", message.msgId, str(exc))
        raise self.retry(exc=exc)

    _log(recipient, template_name, "sent", message.msgId, None)
