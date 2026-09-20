from app import create_app

flask_app = create_app()
celery = flask_app.extensions["celery"]

# imported for their side effect: registering each module's tasks with `celery` above
from app.encryption import tasks as encryption_tasks  # noqa: E402,F401
from app.mailing import tasks as mailing_tasks  # noqa: E402,F401
