from datetime import date
from typing import Optional

from src.extensions import db


class RateUsage(db.Model):
    __tablename__ = 'rate_usage'

    id = db.Column(db.String(36), primary_key=True)
    linkedin_account_id = db.Column(db.String(64), nullable=False, index=True)
    usage_date = db.Column(db.Date, nullable=False, index=True)
    invites_sent = db.Column(db.Integer, nullable=False, default=0)
    messages_sent = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('linkedin_account_id', 'usage_date', name='uq_rate_usage_account_date'),
    )

    @classmethod
    def increment(cls, linkedin_account_id: str, invites: int = 0, messages: int = 0, when: Optional[date] = None):
        usage_day = when or date.today()
        row = (
            db.session.query(cls)
            .filter(cls.linkedin_account_id == linkedin_account_id, cls.usage_date == usage_day)
            .with_for_update(of=cls, nowait=False)
            .first()
        )
        if row is None:
            row = cls(
                id=str(db.func.uuid_generate_v4()) if hasattr(db.func, 'uuid_generate_v4') else str(db.func.gen_random_uuid()) if hasattr(db.func, 'gen_random_uuid') else str(db.func.uuid()),
                linkedin_account_id=linkedin_account_id,
                usage_date=usage_day,
                invites_sent=0,
                messages_sent=0,
            )
            db.session.add(row)
        if invites:
            row.invites_sent = (row.invites_sent or 0) + invites
        if messages:
            row.messages_sent = (row.messages_sent or 0) + messages
        db.session.commit()


