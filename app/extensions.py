from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_smorest import Api
from flask_cors import CORS
from flask_mail import Mail
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
api = Api()
cors = CORS()
mail = Mail()

# One explicit, shared instance that task modules decorate against directly
# (@celery.task(...), not @shared_task) — Celery's @shared_task resolves
# against a *thread-local* "current app", which is only ever set in the
# thread that ran create_app() at startup. Werkzeug's request-handling
# thread doesn't share that thread-local, so @shared_task silently falls
# back to an unconfigured default app there. Binding directly to this one
# instance sidesteps that entirely. create_app() configures it (broker,
# result backend, beat schedule); it's unconfigured until then.
celery = Celery(__name__)