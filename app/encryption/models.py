from app.extensions import db

KEY_LIFETIME_DAYS = 20
GRACE_PERIOD_HOURS = 24


class EncryptionKey(db.Model):
    __tablename__ = "encryption_keys"

    key_version = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wrapped_key = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    activated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.Index(
            "ix_encryption_keys_single_active",
            "is_active",
            unique=True,
            postgresql_where=db.text("is_active = true"),
        ),
    )

    def __repr__(self):
        return f"<EncryptionKey v{self.key_version} active={self.is_active}>"
