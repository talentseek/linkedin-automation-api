"""
Pytest configuration and fixtures for LinkedIn Automation API tests.

This module provides:
- Test database setup and teardown
- Flask test client
- Mock external services
- Common test data
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.main import create_app
from src.extensions import db
from src.models import Client, Campaign, Lead, Event, LinkedInAccount, RateUsage

# Test configuration
TEST_CONFIG = {
    'TESTING': True,
    'DATABASE_URL': 'sqlite:///:memory:',
    'SECRET_KEY': 'test-secret-key',
    'JWT_SECRET_KEY': 'test-jwt-secret',
    'UNIPILE_API_KEY': 'test-unipile-key',
    'UNIPILE_API_BASE_URL': 'https://test-api.unipile.com',
    'RESEND_API_KEY': 'test-resend-key',
    'NOTIFY_EMAIL_FROM': 'test@example.com',
    'NOTIFY_EMAIL_TO': 'test@example.com',
    'CORS_ORIGINS': ['http://localhost:3000'],
    'MAX_CONNECTIONS_PER_DAY': '25',
    'MAX_MESSAGES_PER_DAY': '100',
    'MIN_DELAY_BETWEEN_ACTIONS': '300',
    'MAX_DELAY_BETWEEN_ACTIONS': '1800',
    'WORKING_HOURS_START': '9',
    'WORKING_HOURS_END': '17',
    'LOG_LEVEL': 'DEBUG'
}

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app('testing')
    app.config.update(TEST_CONFIG)
    app.config['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    # Create the database and load test data
    with app.app_context():
        db.create_all()
        yield app
    
    # Clean up the temporary database
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def db_session(app):
    """Database session for tests."""
    with app.app_context():
        yield db.session

@pytest.fixture
def sample_client(db_session):
    """Create a sample client for testing."""
    client = Client(
        name="Test Client",
        email="test@example.com"
    )
    db_session.add(client)
    db_session.commit()
    return client

@pytest.fixture
def sample_linkedin_account(db_session, sample_client):
    """Create a sample LinkedIn account for testing."""
    account = LinkedInAccount(
        client_id=sample_client.id,
        account_id="test-account-123",
        status="connected",
        connected_at=datetime.utcnow()
    )
    db_session.add(account)
    db_session.commit()
    return account

@pytest.fixture
def sample_campaign(db_session, sample_client):
    """Create a sample campaign for testing."""
    campaign = Campaign(
        client_id=sample_client.id,
        name="Test Campaign",
        timezone="UTC",
        status="active",
        sequence_json=[
            {
                "type": "message",
                "content": "Hello {{first_name}}, this is a test message.",
                "delay_days": 1
            }
        ]
    )
    db_session.add(campaign)
    db_session.commit()
    return campaign

@pytest.fixture
def sample_lead(db_session, sample_campaign):
    """Create a sample lead for testing."""
    lead = Lead(
        campaign_id=sample_campaign.id,
        first_name="John",
        last_name="Doe",
        company_name="Test Company",
        public_identifier="john-doe-123",
        provider_id="provider-123",
        status="pending_invite",
        current_step=0
    )
    db_session.add(lead)
    db_session.commit()
    return lead

@pytest.fixture
def sample_event(db_session, sample_lead):
    """Create a sample event for testing."""
    event = Event(
        lead_id=sample_lead.id,
        event_type="invite_sent",
        timestamp=datetime.utcnow(),
        meta_json={"message": "Test invite sent"}
    )
    db_session.add(event)
    db_session.commit()
    return event

@pytest.fixture
def sample_rate_usage(db_session, sample_linkedin_account):
    """Create a sample rate usage record for testing."""
    rate_usage = RateUsage(
        linkedin_account_id=sample_linkedin_account.account_id,
        usage_date=datetime.utcnow().date(),
        invites_sent=5,
        messages_sent=10
    )
    db_session.add(rate_usage)
    db_session.commit()
    return rate_usage

@pytest.fixture
def mock_unipile_client():
    """Mock Unipile client for testing."""
    with patch('src.services.unipile_client.UnipileClient') as mock:
        client_instance = Mock()
        
        # Mock successful responses
        client_instance.get_accounts.return_value = {
            "accounts": [
                {
                    "id": "test-account-123",
                    "status": "connected",
                    "provider": "linkedin"
                }
            ]
        }
        
        client_instance.get_user_profile.return_value = {
            "id": "user-123",
            "public_identifier": "john-doe-123",
            "first_name": "John",
            "last_name": "Doe",
            "company_name": "Test Company"
        }
        
        client_instance.send_connection_request.return_value = {
            "success": True,
            "invitation_id": "invite-123"
        }
        
        client_instance.send_message.return_value = {
            "success": True,
            "message_id": "msg-123"
        }
        
        mock.return_value = client_instance
        yield client_instance

@pytest.fixture
def mock_resend():
    """Mock Resend email service for testing."""
    with patch('src.services.notifications.resend') as mock_resend:
        mock_resend.Emails.send.return_value = {
            "id": "email-123",
            "from": "test@example.com",
            "to": "test@example.com",
            "subject": "Test Email"
        }
        yield mock_resend

@pytest.fixture
def auth_headers():
    """Headers for authenticated requests (when JWT is implemented)."""
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
    }

@pytest.fixture
def json_headers():
    """Headers for JSON requests."""
    return {
        'Content-Type': 'application/json'
    }
