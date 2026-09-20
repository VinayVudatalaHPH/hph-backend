from datetime import datetime, timezone

from flask import current_app, render_template

from app.mailing.tasks import send_email_task


def send_temporary_password_email(user, plaintext_password, is_resend=False):
    """§2's create flow and admin-resend flow share this one function and
    template, swapping the copy via `is_resend` — the delivery mechanism and
    underlying template are identical either way.
    """
    context = {
        "first_name": user.first_name,
        "email": user.email,
        "temp_password": plaintext_password,
        "expires_at": user.temp_password_expires_at,
        "is_resend": is_resend,
        "login_url": current_app.config["FRONTEND_LOGIN_URL"],
    }
    subject = "Your Vitalyse Health password was reset" if is_resend else "Welcome to Vitalyse Health"

    send_email_task.delay(
        recipient=user.email,
        subject=subject,
        html_body=render_template("mailing/temporary_password.html", **context),
        text_body=render_template("mailing/temporary_password.txt", **context),
        template_name="temporary_password",
    )


def send_password_changed_confirmation(user):
    context = {"first_name": user.first_name, "changed_at": datetime.now(timezone.utc)}

    send_email_task.delay(
        recipient=user.email,
        subject="Your Vitalyse Health password was changed",
        html_body=render_template("mailing/password_changed.html", **context),
        text_body=render_template("mailing/password_changed.txt", **context),
        template_name="password_changed",
    )
