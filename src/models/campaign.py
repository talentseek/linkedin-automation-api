import uuid
from datetime import datetime
from src.models import db
from sqlalchemy import JSON


class Campaign(db.Model):
    __tablename__ = 'campaigns'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    timezone = db.Column(db.String(50), nullable=False, default='UTC')  # IANA timezone format
    sequence_json = db.Column(JSON, nullable=True)  # Sequence definition as JSON
    status = db.Column(db.String(50), nullable=False, default='draft')  # draft, active, paused, completed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    leads = db.relationship('Lead', backref='campaign', lazy=True, cascade='all, delete-orphan')
    
    @property
    def sequence(self):
        """Get the sequence as a list of steps."""
        return self.sequence_json or []
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'name': self.name,
            'timezone': self.timezone,
            'sequence_json': self.sequence_json,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Campaign {self.name}>'

