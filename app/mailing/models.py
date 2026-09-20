from app.extensions import db


class EmailLog(db.Model):
    __tablename__ = "email_logs"

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(255), nullable=False)
    template_name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False)  # "sent" / "failed"
    # Our own Message-ID (email.utils.make_msgid(), via Flask-Mail's
    # Message.msgId) — the closest equivalent to a cloud provider's message
    # id when sending over raw SMTP rather than a provider API.
    provider_message_id = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    def __repr__(self):
        return f"<EmailLog {self.template_name} -> {self.recipient} [{self.status}]>"
