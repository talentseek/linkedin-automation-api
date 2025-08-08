import uuid
from datetime import datetime
from src.models import db


class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    linkedin_accounts = db.relationship('LinkedInAccount', backref='client', lazy=True, cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Client {self.name}>'

