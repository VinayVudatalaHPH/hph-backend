from email.utils import parseaddr
from urllib.parse import urlparse


def validate_mail_config(config):
    """Validate SMTP settings without opening a connection or exposing secrets."""
    errors = []

    if config["MAIL_USE_TLS"] and config["MAIL_USE_SSL"]:
        errors.append("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled")

    if not config["MAIL_SERVER"]:
        errors.append("EMAIL_HOST is required")
    elif config["MAIL_SERVER"].lower() in {"localhost", "127.0.0.1", "mailpit"}:
        errors.append("EMAIL_HOST must not point to Mailpit/localhost outside local development")

    if not 1 <= config["MAIL_PORT"] <= 65535:
        errors.append("EMAIL_PORT must be between 1 and 65535")

    username_set = bool(config["MAIL_USERNAME"])
    password_set = bool(config["MAIL_PASSWORD"])
    if username_set != password_set:
        errors.append("EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set together")

    sender = config["MAIL_DEFAULT_SENDER"] or ""
    sender_address = parseaddr(sender)[1]
    sender_domain = sender_address.rpartition("@")[2].lower()
    if not sender_address or "@" not in sender_address:
        errors.append("DEFAULT_FROM_EMAIL must be a valid email address")
    elif sender_domain.endswith((".example", ".invalid", ".localhost", ".test")):
        errors.append("DEFAULT_FROM_EMAIL must not use a reserved placeholder domain")

    login_url = config["FRONTEND_LOGIN_URL"] or ""
    parsed_login_url = urlparse(login_url)
    if parsed_login_url.scheme != "https" or not parsed_login_url.netloc:
        errors.append("FRONTEND_LOGIN_URL must be an absolute HTTPS URL outside local development")

    if errors:
        formatted_errors = "\n- ".join(errors)
        raise RuntimeError(f"Invalid mail configuration:\n- {formatted_errors}")
