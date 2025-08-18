import uuid
from datetime import datetime
from src.models import db
from sqlalchemy import JSON


class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = db.Column(db.String(36), db.ForeignKey('leads.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  
    # Event types: invite_sent, message_sent, connection_accepted, reply_received, error, etc.
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    meta_json = db.Column(JSON, nullable=True)  # Additional event data, error details, etc.
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'lead_id': str(self.lead_id),
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'meta_json': self.meta_json
        }
    
    def __repr__(self):
        return f'<Event {self.event_type} for Lead {self.lead_id}>'

