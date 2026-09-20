from celery.schedules import crontab

from app.extensions import celery


def make_celery(flask_app):
    celery.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=flask_app.config["CELERY_TASK_ALWAYS_EAGER"],
        task_eager_propagates=True,
        beat_schedule={
            # §4b: "a scheduled Celery Beat task checks daily and rotates
            # once now() >= active_key.expires_at". The task itself is a
            # no-op on days rotation isn't due (rotate_key(force=False)).
            "check-and-rotate-encryption-key-daily": {
                "task": "encryption.check_and_rotate_key",
                "schedule": crontab(hour=0, minute=0),
            },
        },
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
