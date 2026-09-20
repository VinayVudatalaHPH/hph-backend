import pytest

from app.mailing.config import validate_mail_config


def _valid_config(**overrides):
    config = {
        "MAIL_SERVER": "smtp.example.com",
        "MAIL_PORT": 587,
        "MAIL_USE_TLS": True,
        "MAIL_USE_SSL": False,
        "MAIL_USERNAME": "smtp-user",
        "MAIL_PASSWORD": "smtp-password",
        "MAIL_DEFAULT_SENDER": "noreply@example.com",
        "FRONTEND_LOGIN_URL": "https://testing.example.com/login",
    }
    config.update(overrides)
    return config


def test_validate_mail_config_accepts_testing_smtp_settings():
    validate_mail_config(_valid_config())


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"MAIL_SERVER": "localhost"}, "must not point to Mailpit/localhost"),
        ({"MAIL_USE_SSL": True}, "cannot both be enabled"),
        ({"MAIL_PASSWORD": None}, "must be set together"),
        ({"MAIL_DEFAULT_SENDER": "not-an-email"}, "must be a valid email address"),
        (
            {"MAIL_DEFAULT_SENDER": "noreply@your-domain.example"},
            "must not use a reserved placeholder domain",
        ),
        ({"FRONTEND_LOGIN_URL": "http://testing.example.com/login"}, "absolute HTTPS URL"),
    ],
)
def test_validate_mail_config_rejects_unsafe_deployment_settings(overrides, expected):
    with pytest.raises(RuntimeError, match=expected):
        validate_mail_config(_valid_config(**overrides))


def test_send_email_task_sends_and_records_success(monkeypatch, app):
    from app.mailing import tasks

    sent_messages = []
    log_calls = []
    monkeypatch.setattr(tasks.mail, "send", sent_messages.append)
    monkeypatch.setattr(tasks, "_log", lambda *args: log_calls.append(args))

    with app.app_context():
        tasks.send_email_task.run(
            "person@example.com",
            "Subject",
            "<p>Body</p>",
            "Body",
            "test_template",
        )

    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message.recipients == ["person@example.com"]
    assert message.sender == app.config["MAIL_DEFAULT_SENDER"]
    assert log_calls == [
        ("person@example.com", "test_template", "sent", message.msgId, None)
    ]
