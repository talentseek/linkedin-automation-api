# Import db from extensions to use the same instance
from src.extensions import db

# Import all models to ensure they are registered with SQLAlchemy
from src.models.client import Client
from src.models.linkedin_account import LinkedInAccount
from src.models.campaign import Campaign
from src.models.lead import Lead
from src.models.event import Event
from src.models.webhook import Webhook
from src.models.webhook_data import WebhookData
from src.models.rate_usage import RateUsage

__all__ = ['db', 'Client', 'LinkedInAccount', 'Campaign', 'Lead', 'Event', 'Webhook', 'WebhookData', 'RateUsage']

