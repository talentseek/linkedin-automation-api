import uuid
from datetime import datetime
from src.models import db


class LinkedInAccount(db.Model):
    __tablename__ = 'linkedin_accounts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    account_id = db.Column(db.String(255), nullable=False, unique=True)  # Unipile's account ID
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, connected, disconnected, error
    connected_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    webhooks = db.relationship('Webhook', backref='linkedin_account', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'account_id': self.account_id,
            'status': self.status,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None
        }
    
    def __repr__(self):
        return f'<LinkedInAccount {self.account_id}>'

