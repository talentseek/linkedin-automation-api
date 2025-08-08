import uuid
from datetime import datetime
from src.models import db


class Webhook(db.Model):
    __tablename__ = 'webhooks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('linkedin_accounts.id'), nullable=False)
    source = db.Column(db.String(50), nullable=False)  # 'users' or 'messaging'
    webhook_id = db.Column(db.String(255), nullable=False)  # Webhook ID from Unipile
    status = db.Column(db.String(50), nullable=False, default='active')  # active, inactive, error
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'account_id': str(self.account_id),
            'source': self.source,
            'webhook_id': self.webhook_id,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Webhook {self.webhook_id} ({self.source})>'

