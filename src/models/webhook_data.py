from datetime import datetime
from src.extensions import db
import uuid
import json


class WebhookData(db.Model):
    __tablename__ = 'webhook_data'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    method = db.Column(db.String(10), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.Text, nullable=True)  # JSON string
    raw_data = db.Column(db.Text, nullable=True)
    json_data = db.Column(db.Text, nullable=True)  # JSON string
    content_type = db.Column(db.String(100), nullable=True)
    content_length = db.Column(db.Integer, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'method': self.method,
            'url': self.url,
            'headers': json.loads(self.headers) if self.headers else None,
            'raw_data': self.raw_data,
            'json_data': json.loads(self.json_data) if self.json_data else None,
            'content_type': self.content_type,
            'content_length': self.content_length
        }
