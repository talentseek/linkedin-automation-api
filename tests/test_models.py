"""
Unit tests for database models.

This module tests:
- Model creation and validation
- Model relationships
- Model methods and properties
- Database constraints
"""

import pytest
from datetime import datetime, date
from sqlalchemy.exc import IntegrityError

from src.models import Client, Campaign, Lead, Event, LinkedInAccount, RateUsage


@pytest.mark.unit
class TestClient:
    """Test Client model."""
    
    def test_create_client(self, db_session):
        """Test creating a client."""
        client = Client(name="Test Client", email="test@example.com")
        db_session.add(client)
        db_session.commit()
        
        assert client.id is not None
        assert client.name == "Test Client"
        assert client.email == "test@example.com"
        assert client.created_at is not None
    
    def test_client_to_dict(self, db_session):
        """Test client to_dict method."""
        client = Client(name="Test Client", email="test@example.com")
        db_session.add(client)
        db_session.commit()
        
        client_dict = client.to_dict()
        
        assert client_dict['id'] == client.id
        assert client_dict['name'] == "Test Client"
        assert client_dict['email'] == "test@example.com"
        assert 'created_at' in client_dict
    
    def test_client_relationships(self, db_session, sample_client, sample_campaign, sample_linkedin_account):
        """Test client relationships."""
        # Test campaigns relationship
        assert len(sample_client.campaigns) == 1
        assert sample_client.campaigns[0].id == sample_campaign.id
        
        # Test LinkedIn accounts relationship
        assert len(sample_client.linkedin_accounts) == 1
        assert sample_client.linkedin_accounts[0].id == sample_linkedin_account.id


class TestCampaign:
    """Test Campaign model."""
    
    def test_create_campaign(self, db_session, sample_client):
        """Test creating a campaign."""
        sequence = [
            {
                "type": "message",
                "content": "Hello {{first_name}}!",
                "delay_days": 1
            }
        ]
        
        campaign = Campaign(
            client_id=sample_client.id,
            name="Test Campaign",
            timezone="UTC",
            status="active",
            sequence_json=sequence
        )
        db_session.add(campaign)
        db_session.commit()
        
        assert campaign.id is not None
        assert campaign.name == "Test Campaign"
        assert campaign.timezone == "UTC"
        assert campaign.status == "active"
        assert campaign.sequence == sequence
    
    def test_campaign_sequence_property(self, db_session, sample_client):
        """Test campaign sequence property."""
        sequence = [{"type": "message", "content": "Test"}]
        campaign = Campaign(
            client_id=sample_client.id,
            name="Test Campaign",
            sequence_json=sequence
        )
        db_session.add(campaign)
        db_session.commit()
        
        assert campaign.sequence == sequence
    
    def test_campaign_sequence_empty(self, db_session, sample_client):
        """Test campaign sequence property with empty sequence."""
        campaign = Campaign(
            client_id=sample_client.id,
            name="Test Campaign"
        )
        db_session.add(campaign)
        db_session.commit()
        
        assert campaign.sequence == []
    
    def test_campaign_to_dict(self, db_session, sample_client):
        """Test campaign to_dict method."""
        campaign = Campaign(
            client_id=sample_client.id,
            name="Test Campaign",
            timezone="UTC",
            status="active"
        )
        db_session.add(campaign)
        db_session.commit()
        
        campaign_dict = campaign.to_dict()
        
        assert campaign_dict['id'] == campaign.id
        assert campaign_dict['name'] == "Test Campaign"
        assert campaign_dict['timezone'] == "UTC"
        assert campaign_dict['status'] == "active"
        assert 'created_at' in campaign_dict


class TestLead:
    """Test Lead model."""
    
    def test_create_lead(self, db_session, sample_campaign):
        """Test creating a lead."""
        lead = Lead(
            campaign_id=sample_campaign.id,
            first_name="John",
            last_name="Doe",
            company_name="Test Company",
            public_identifier="john-doe-123",
            provider_id="provider-123",
            status="pending_invite"
        )
        db_session.add(lead)
        db_session.commit()
        
        assert lead.id is not None
        assert lead.first_name == "John"
        assert lead.last_name == "Doe"
        assert lead.company_name == "Test Company"
        assert lead.public_identifier == "john-doe-123"
        assert lead.status == "pending_invite"
        assert lead.current_step == 0
    
    def test_lead_unique_constraint(self, db_session, sample_campaign):
        """Test lead unique constraint on campaign_id + public_identifier."""
        # Create first lead
        lead1 = Lead(
            campaign_id=sample_campaign.id,
            public_identifier="john-doe-123",
            status="pending_invite"
        )
        db_session.add(lead1)
        db_session.commit()
        
        # Try to create duplicate lead
        lead2 = Lead(
            campaign_id=sample_campaign.id,
            public_identifier="john-doe-123",  # Same identifier
            status="pending_invite"
        )
        db_session.add(lead2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_lead_to_dict(self, db_session, sample_campaign):
        """Test lead to_dict method."""
        lead = Lead(
            campaign_id=sample_campaign.id,
            first_name="John",
            last_name="Doe",
            public_identifier="john-doe-123",
            status="pending_invite"
        )
        db_session.add(lead)
        db_session.commit()
        
        lead_dict = lead.to_dict()
        
        assert lead_dict['id'] == lead.id
        assert lead_dict['first_name'] == "John"
        assert lead_dict['last_name'] == "Doe"
        assert lead_dict['public_identifier'] == "john-doe-123"
        assert lead_dict['status'] == "pending_invite"
        assert 'created_at' in lead_dict


class TestEvent:
    """Test Event model."""
    
    def test_create_event(self, db_session, sample_lead):
        """Test creating an event."""
        event = Event(
            lead_id=sample_lead.id,
            event_type="invite_sent",
            meta_json={"message": "Test invite sent"}
        )
        db_session.add(event)
        db_session.commit()
        
        assert event.id is not None
        assert event.lead_id == sample_lead.id
        assert event.event_type == "invite_sent"
        assert event.meta_json["message"] == "Test invite sent"
        assert event.timestamp is not None
    
    def test_event_to_dict(self, db_session, sample_lead):
        """Test event to_dict method."""
        event = Event(
            lead_id=sample_lead.id,
            event_type="invite_sent",
            meta_json={"message": "Test"}
        )
        db_session.add(event)
        db_session.commit()
        
        event_dict = event.to_dict()
        
        assert event_dict['id'] == event.id
        assert event_dict['lead_id'] == sample_lead.id
        assert event_dict['event_type'] == "invite_sent"
        assert event_dict['meta_json']['message'] == "Test"
        assert 'timestamp' in event_dict


class TestLinkedInAccount:
    """Test LinkedInAccount model."""
    
    def test_create_linkedin_account(self, db_session, sample_client):
        """Test creating a LinkedIn account."""
        account = LinkedInAccount(
            client_id=sample_client.id,
            account_id="test-account-123",
            status="connected",
            connected_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.commit()
        
        assert account.id is not None
        assert account.client_id == sample_client.id
        assert account.account_id == "test-account-123"
        assert account.status == "connected"
        assert account.connected_at is not None
    
    def test_account_id_unique_constraint(self, db_session, sample_client):
        """Test account_id unique constraint."""
        # Create first account
        account1 = LinkedInAccount(
            client_id=sample_client.id,
            account_id="test-account-123",
            status="connected"
        )
        db_session.add(account1)
        db_session.commit()
        
        # Try to create duplicate account
        account2 = LinkedInAccount(
            client_id=sample_client.id,
            account_id="test-account-123",  # Same account_id
            status="connected"
        )
        db_session.add(account2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_linkedin_account_to_dict(self, db_session, sample_client):
        """Test LinkedInAccount to_dict method."""
        account = LinkedInAccount(
            client_id=sample_client.id,
            account_id="test-account-123",
            status="connected"
        )
        db_session.add(account)
        db_session.commit()
        
        account_dict = account.to_dict()
        
        assert account_dict['id'] == account.id
        assert account_dict['client_id'] == sample_client.id
        assert account_dict['account_id'] == "test-account-123"
        assert account_dict['status'] == "connected"


class TestRateUsage:
    """Test RateUsage model."""
    
    def test_create_rate_usage(self, db_session):
        """Test creating a rate usage record."""
        usage = RateUsage(
            linkedin_account_id="test-account-123",
            usage_date=date.today(),
            invites_sent=5,
            messages_sent=10
        )
        db_session.add(usage)
        db_session.commit()
        
        assert usage.id is not None
        assert usage.linkedin_account_id == "test-account-123"
        assert usage.usage_date == date.today()
        assert usage.invites_sent == 5
        assert usage.messages_sent == 10
    
    def test_rate_usage_unique_constraint(self, db_session):
        """Test unique constraint on linkedin_account_id + usage_date."""
        today = date.today()
        
        # Create first record
        usage1 = RateUsage(
            linkedin_account_id="test-account-123",
            usage_date=today,
            invites_sent=5,
            messages_sent=10
        )
        db_session.add(usage1)
        db_session.commit()
        
        # Try to create duplicate record
        usage2 = RateUsage(
            linkedin_account_id="test-account-123",  # Same account
            usage_date=today,  # Same date
            invites_sent=3,
            messages_sent=7
        )
        db_session.add(usage2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_rate_usage_increment_method(self, db_session):
        """Test RateUsage.increment class method."""
        today = date.today()
        account_id = "test-account-123"
        
        # Increment invites
        RateUsage.increment(account_id, invites=5)
        
        # Check record was created
        usage = db_session.query(RateUsage).filter_by(
            linkedin_account_id=account_id,
            usage_date=today
        ).first()
        
        assert usage is not None
        assert usage.invites_sent == 5
        assert usage.messages_sent == 0
        
        # Increment messages
        RateUsage.increment(account_id, messages=10)
        
        # Check record was updated
        usage = db_session.query(RateUsage).filter_by(
            linkedin_account_id=account_id,
            usage_date=today
        ).first()
        
        assert usage.invites_sent == 5
        assert usage.messages_sent == 10
