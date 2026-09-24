from app.extensions import db


class OfficeHoliday(db.Model):
    __tablename__ = "office_holidays"

    id = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(32), nullable=False, default="public")
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

