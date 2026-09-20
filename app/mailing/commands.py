import click

from app.mailing.config import validate_mail_config
from app.mailing.tasks import send_email_task


@click.command("mail-smoke-test")
@click.argument("recipient")
def mail_smoke_test_command(recipient):
    """Validate mail config and enqueue a delivery through the real worker."""
    from flask import current_app

    validate_mail_config(current_app.config)
    result = send_email_task.delay(
        recipient=recipient,
        subject="Vitalyse Health testing environment mail check",
        html_body=(
            "<p>Vitalyse Health email delivery is configured correctly for this environment.</p>"
        ),
        text_body="Vitalyse Health email delivery is configured correctly for this environment.",
        template_name="deployment_smoke_test",
    )
    click.echo(f"Queued mail smoke test (task {result.id}).")
    click.echo("Confirm delivery and a 'sent' email_logs row; the Celery worker performs the SMTP send.")
