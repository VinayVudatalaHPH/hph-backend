from app.encryption.services import rotate_key
from app.extensions import celery


@celery.task(name="encryption.check_and_rotate_key")
def check_and_rotate_encryption_key_task():
    """Daily Beat check (§4b). force=False, so this is a safe no-op on every
    day the active key hasn't actually reached its 20-day expiry yet.
    """
    rotate_key(force=False)
