"""seed initial encryption key

Revision ID: 870ae9e6f14c
Revises: e3b43d8e6451
Create Date: 2026-09-17 07:50:24.857351

"""
import base64
import os
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# revision identifiers, used by Alembic.
revision = '870ae9e6f14c'
down_revision = 'e3b43d8e6451'
branch_labels = None
depends_on = None

KEY_LIFETIME_DAYS = 20
NONCE_SIZE = 12

encryption_keys_table = sa.table(
    "encryption_keys",
    sa.column("wrapped_key", sa.LargeBinary),
    sa.column("activated_at", sa.DateTime(timezone=True)),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("is_active", sa.Boolean),
)


def _wrap_key(raw_key):
    master_key = base64.b64decode(os.environ["ENCRYPTION_MASTER_KEY"])
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, raw_key, None)


def upgrade():
    now = datetime.now(timezone.utc)
    raw_key = AESGCM.generate_key(bit_length=256)

    op.bulk_insert(
        encryption_keys_table,
        [
            {
                "wrapped_key": _wrap_key(raw_key),
                "activated_at": now,
                "expires_at": now + timedelta(days=KEY_LIFETIME_DAYS),
                "is_active": True,
            }
        ],
    )


def downgrade():
    op.execute(encryption_keys_table.delete())
