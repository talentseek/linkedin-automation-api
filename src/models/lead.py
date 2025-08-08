import uuid
from datetime import datetime
from src.models import db
from sqlalchemy import UniqueConstraint


class Lead(db.Model):
    __tablename__ = 'leads'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = db.Column(db.String(36), db.ForeignKey('campaigns.id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    company_name = db.Column(db.String(255), nullable=True)
    public_identifier = db.Column(db.String(255), nullable=False)  # LinkedIn public identifier
    provider_id = db.Column(db.String(255), nullable=True)  # Unipile's internal provider ID
    conversation_id = db.Column(db.String(255), nullable=True)  # LinkedIn conversation ID for messaging
    status = db.Column(db.String(50), nullable=False, default='pending_invite')  
    # Status options: pending_invite, invited, connected, responded, completed, error
    last_step_sent_at = db.Column(db.DateTime, nullable=True)
    current_step = db.Column(db.Integer, nullable=False, default=0)  # Current step in sequence (0-based)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    events = db.relationship('Event', backref='lead', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint to prevent duplicates within the same campaign
    __table_args__ = (
        UniqueConstraint('campaign_id', 'public_identifier', name='uq_campaign_public_identifier'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'campaign_id': str(self.campaign_id),
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company_name': self.company_name,
            'public_identifier': self.public_identifier,
            'provider_id': self.provider_id,
            'status': self.status,
            'last_step_sent_at': self.last_step_sent_at.isoformat() if self.last_step_sent_at else None,
            'current_step': self.current_step,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return "Unknown"
    
    @classmethod
    def find_duplicates_across_campaigns(cls, public_identifier: str, client_id: str = None):
        """
        Find all leads with the same public_identifier across campaigns.
        
        Args:
            public_identifier: LinkedIn public identifier
            client_id: Optional client ID to limit search to specific client
            
        Returns:
            List of Lead objects with the same public_identifier
        """
        query = cls.query.filter_by(public_identifier=public_identifier)
        
        if client_id:
            # Join with campaigns to filter by client
            from src.models.campaign import Campaign
            query = query.join(Campaign).filter(Campaign.client_id == client_id)
        
        return query.all()
    
    @classmethod
    def find_duplicates_in_campaign(cls, public_identifier: str, campaign_id: str):
        """
        Find leads with the same public_identifier in a specific campaign.
        
        Args:
            public_identifier: LinkedIn public identifier
            campaign_id: Campaign ID to search in
            
        Returns:
            Lead object if found, None otherwise
        """
        return cls.query.filter_by(
            public_identifier=public_identifier,
            campaign_id=campaign_id
        ).first()
    
    def __repr__(self):
        return f'<Lead {self.full_name} ({self.public_identifier})>'

