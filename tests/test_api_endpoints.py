"""
Unit tests for API Endpoints.

This module tests all API endpoints including authentication, request handling,
response formatting, and error scenarios.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from flask import Flask
from src.main import create_app
from src.models import Client, LinkedInAccount, Campaign, Lead, Event


class TestAuthEndpoints:
    """Test cases for authentication endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_register_success(self, client):
        """Test successful user registration."""
        with patch('src.routes.auth.User') as mock_user:
            mock_user.query.filter_by.return_value.first.return_value = None
            
            response = client.post('/api/v1/auth/register', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'message' in data
            assert 'user_id' in data

    def test_register_existing_user(self, client):
        """Test registration with existing email."""
        with patch('src.routes.auth.User') as mock_user:
            mock_user.query.filter_by.return_value.first.return_value = Mock()
            
            response = client.post('/api/v1/auth/register', json={
                'email': 'existing@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'error' in data

    def test_login_success(self, client):
        """Test successful user login."""
        mock_user = Mock()
        mock_user.verify_password.return_value = True
        mock_user.id = 1
        mock_user.email = 'test@example.com'
        
        with patch('src.routes.auth.User') as mock_user_class:
            mock_user_class.query.filter_by.return_value.first.return_value = mock_user
            
            response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'access_token' in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        with patch('src.routes.auth.User') as mock_user:
            mock_user.query.filter_by.return_value.first.return_value = None
            
            response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'wrongpassword'
            })
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert 'error' in data

    def test_logout(self, client):
        """Test user logout."""
        with patch('src.routes.auth.jwt') as mock_jwt:
            mock_jwt.get_jwt.return_value = {'jti': 'token123'}
            
            response = client.post('/api/v1/auth/logout')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'message' in data


class TestLinkedInEndpoints:
    """Test cases for LinkedIn-related endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def auth_headers(self):
        """Create authenticated headers."""
        return {'Authorization': 'Bearer test_token'}

    def test_get_linkedin_accounts(self, client, auth_headers):
        """Test getting LinkedIn accounts."""
        mock_accounts = [
            Mock(id=1, account_id='account1', account_name='Account 1'),
            Mock(id=2, account_id='account2', account_name='Account 2')
        ]
        
        with patch('src.routes.linkedin_account.LinkedInAccount') as mock_account_class:
            mock_account_class.query.filter_by.return_value.all.return_value = mock_accounts
            
            response = client.get('/api/v1/linkedin-accounts', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['accounts']) == 2

    def test_get_linkedin_account(self, client, auth_headers):
        """Test getting a specific LinkedIn account."""
        mock_account = Mock(id=1, account_id='account1', account_name='Account 1')
        
        with patch('src.routes.linkedin_account.LinkedInAccount') as mock_account_class:
            mock_account_class.query.get.return_value = mock_account
            
            response = client.get('/api/v1/linkedin-accounts/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['account']['account_id'] == 'account1'

    def test_create_linkedin_account(self, client, auth_headers):
        """Test creating a LinkedIn account."""
        with patch('src.routes.linkedin_account.LinkedInAccount') as mock_account_class:
            mock_account = Mock(id=1, account_id='new-account')
            mock_account_class.return_value = mock_account
            
            response = client.post('/api/v1/linkedin-accounts', 
                                 json={'account_id': 'new-account'},
                                 headers=auth_headers)
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'account' in data

    def test_update_linkedin_account(self, client, auth_headers):
        """Test updating a LinkedIn account."""
        mock_account = Mock(id=1, account_id='account1')
        
        with patch('src.routes.linkedin_account.LinkedInAccount') as mock_account_class:
            mock_account_class.query.get.return_value = mock_account
            
            response = client.put('/api/v1/linkedin-accounts/1',
                                json={'account_name': 'Updated Account'},
                                headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'account' in data

    def test_delete_linkedin_account(self, client, auth_headers):
        """Test deleting a LinkedIn account."""
        mock_account = Mock(id=1, account_id='account1')
        
        with patch('src.routes.linkedin_account.LinkedInAccount') as mock_account_class:
            mock_account_class.query.get.return_value = mock_account
            
            response = client.delete('/api/v1/linkedin-accounts/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'message' in data


class TestCampaignEndpoints:
    """Test cases for campaign endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def auth_headers(self):
        """Create authenticated headers."""
        return {'Authorization': 'Bearer test_token'}

    def test_get_campaigns(self, client, auth_headers):
        """Test getting campaigns."""
        mock_campaigns = [
            Mock(id=1, name='Campaign 1', is_active=True),
            Mock(id=2, name='Campaign 2', is_active=False)
        ]
        
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign_class.query.filter_by.return_value.all.return_value = mock_campaigns
            
            response = client.get('/api/v1/campaigns', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['campaigns']) == 2

    def test_get_campaign(self, client, auth_headers):
        """Test getting a specific campaign."""
        mock_campaign = Mock(id=1, name='Test Campaign', is_active=True)
        
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign_class.query.get.return_value = mock_campaign
            
            response = client.get('/api/v1/campaigns/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['campaign']['name'] == 'Test Campaign'

    def test_create_campaign(self, client, auth_headers):
        """Test creating a campaign."""
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign = Mock(id=1, name='New Campaign')
            mock_campaign_class.return_value = mock_campaign
            
            response = client.post('/api/v1/campaigns',
                                 json={'name': 'New Campaign'},
                                 headers=auth_headers)
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'campaign' in data

    def test_update_campaign(self, client, auth_headers):
        """Test updating a campaign."""
        mock_campaign = Mock(id=1, name='Test Campaign')
        
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign_class.query.get.return_value = mock_campaign
            
            response = client.put('/api/v1/campaigns/1',
                                json={'name': 'Updated Campaign'},
                                headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'campaign' in data

    def test_delete_campaign(self, client, auth_headers):
        """Test deleting a campaign."""
        mock_campaign = Mock(id=1, name='Test Campaign')
        
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign_class.query.get.return_value = mock_campaign
            
            response = client.delete('/api/v1/campaigns/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'message' in data

    def test_campaign_statistics(self, client, auth_headers):
        """Test getting campaign statistics."""
        mock_campaign = Mock(id=1, name='Test Campaign')
        mock_campaign.get_lead_count.return_value = 50
        mock_campaign.get_connection_rate.return_value = 25.5
        
        with patch('src.routes.campaign.Campaign') as mock_campaign_class:
            mock_campaign_class.query.get.return_value = mock_campaign
            
            response = client.get('/api/v1/campaigns/1/statistics', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'statistics' in data


class TestLeadEndpoints:
    """Test cases for lead endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def auth_headers(self):
        """Create authenticated headers."""
        return {'Authorization': 'Bearer test_token'}

    def test_get_leads(self, client, auth_headers):
        """Test getting leads."""
        mock_leads = [
            Mock(id=1, first_name='John', last_name='Doe', status='pending'),
            Mock(id=2, first_name='Jane', last_name='Smith', status='connected')
        ]
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.filter_by.return_value.all.return_value = mock_leads
            
            response = client.get('/api/v1/leads', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['leads']) == 2

    def test_get_lead(self, client, auth_headers):
        """Test getting a specific lead."""
        mock_lead = Mock(id=1, first_name='John', last_name='Doe', status='pending')
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.get.return_value = mock_lead
            
            response = client.get('/api/v1/leads/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['lead']['first_name'] == 'John'

    def test_create_lead(self, client, auth_headers):
        """Test creating a lead."""
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead = Mock(id=1, first_name='New', last_name='Lead')
            mock_lead_class.return_value = mock_lead
            
            response = client.post('/api/v1/leads',
                                 json={'first_name': 'New', 'last_name': 'Lead'},
                                 headers=auth_headers)
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'lead' in data

    def test_update_lead(self, client, auth_headers):
        """Test updating a lead."""
        mock_lead = Mock(id=1, first_name='John', last_name='Doe')
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.get.return_value = mock_lead
            
            response = client.put('/api/v1/leads/1',
                                json={'first_name': 'John Updated'},
                                headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'lead' in data

    def test_delete_lead(self, client, auth_headers):
        """Test deleting a lead."""
        mock_lead = Mock(id=1, first_name='John', last_name='Doe')
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.get.return_value = mock_lead
            
            response = client.delete('/api/v1/leads/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'message' in data

    def test_send_connection_request(self, client, auth_headers):
        """Test sending connection request to a lead."""
        mock_lead = Mock(id=1, first_name='John', last_name='Doe')
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.get.return_value = mock_lead
            
            with patch('src.routes.lead.crud.UnipileClient') as mock_client:
                mock_client.return_value.send_connection_request.return_value = {'id': 'invitation-123'}
                
                response = client.post('/api/v1/leads/1/send-connection',
                                     json={'message': 'Would you like to connect?'},
                                     headers=auth_headers)
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'message' in data

    def test_send_message(self, client, auth_headers):
        """Test sending message to a lead."""
        mock_lead = Mock(id=1, first_name='John', last_name='Doe')
        
        with patch('src.routes.lead.crud.Lead') as mock_lead_class:
            mock_lead_class.query.get.return_value = mock_lead
            
            with patch('src.routes.lead.crud.UnipileClient') as mock_client:
                mock_client.return_value.send_message.return_value = {'id': 'message-123'}
                
                response = client.post('/api/v1/leads/1/send-message',
                                     json={'content': 'Hello, how are you?'},
                                     headers=auth_headers)
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'message' in data


class TestWebhookEndpoints:
    """Test cases for webhook endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_webhook_connection_accepted(self, client):
        """Test webhook for connection accepted."""
        webhook_data = {
            'event_type': 'connection_accepted',
            'data': {
                'lead_id': 123,
                'account_id': 'test-account'
            }
        }
        
        with patch('src.routes.webhook.handlers.handle_connection_accepted') as mock_handler:
            response = client.post('/api/v1/webhooks/linkedin',
                                 json=webhook_data,
                                 content_type='application/json')
            
            assert response.status_code == 200
            mock_handler.assert_called_once()

    def test_webhook_connection_rejected(self, client):
        """Test webhook for connection rejected."""
        webhook_data = {
            'event_type': 'connection_rejected',
            'data': {
                'lead_id': 123,
                'account_id': 'test-account'
            }
        }
        
        with patch('src.routes.webhook.handlers.handle_connection_rejected') as mock_handler:
            response = client.post('/api/v1/webhooks/linkedin',
                                 json=webhook_data,
                                 content_type='application/json')
            
            assert response.status_code == 200
            mock_handler.assert_called_once()

    def test_webhook_message_received(self, client):
        """Test webhook for message received."""
        webhook_data = {
            'event_type': 'message_received',
            'data': {
                'lead_id': 123,
                'message': 'Hello, thanks for connecting!',
                'account_id': 'test-account'
            }
        }
        
        with patch('src.routes.webhook.handlers.handle_message_received') as mock_handler:
            response = client.post('/api/v1/webhooks/linkedin',
                                 json=webhook_data,
                                 content_type='application/json')
            
            assert response.status_code == 200
            mock_handler.assert_called_once()

    def test_webhook_invalid_event_type(self, client):
        """Test webhook with invalid event type."""
        webhook_data = {
            'event_type': 'invalid_event',
            'data': {}
        }
        
        response = client.post('/api/v1/webhooks/linkedin',
                             json=webhook_data,
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_webhook_missing_data(self, client):
        """Test webhook with missing data."""
        webhook_data = {
            'event_type': 'connection_accepted'
            # Missing data field
        }
        
        response = client.post('/api/v1/webhooks/linkedin',
                             json=webhook_data,
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestAnalyticsEndpoints:
    """Test cases for analytics endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def auth_headers(self):
        """Create authenticated headers."""
        return {'Authorization': 'Bearer test_token'}

    def test_get_weekly_statistics(self, client, auth_headers):
        """Test getting weekly statistics."""
        mock_stats = [
            Mock(week_start_date=datetime.now().date(), total_leads=100, connections_sent=50),
            Mock(week_start_date=(datetime.now() - timedelta(days=7)).date(), total_leads=80, connections_sent=40)
        ]
        
        with patch('src.routes.analytics.weekly_statistics.WeeklyStatistics') as mock_stats_class:
            mock_stats_class.query.order_by.return_value.limit.return_value.all.return_value = mock_stats
            
            response = client.get('/api/v1/analytics/weekly', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'statistics' in data

    def test_get_campaign_analytics(self, client, auth_headers):
        """Test getting campaign analytics."""
        mock_campaign = Mock(id=1, name='Test Campaign')
        mock_campaign.get_lead_count.return_value = 50
        mock_campaign.get_connection_rate.return_value = 25.5
        
        with patch('src.routes.analytics.campaign_analytics.Campaign') as mock_campaign_class:
            mock_campaign_class.query.get.return_value = mock_campaign
            
            response = client.get('/api/v1/analytics/campaigns/1', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'analytics' in data

    def test_get_user_analytics(self, client, auth_headers):
        """Test getting user analytics."""
        mock_user = Mock(id=1, email='test@example.com')
        
        with patch('src.routes.analytics.core.User') as mock_user_class:
            mock_user_class.query.get.return_value = mock_user
            
            response = client.get('/api/v1/analytics/user', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'analytics' in data


class TestErrorHandling:
    """Test cases for error handling."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_404_error(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-endpoint')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_500_error(self, client):
        """Test 500 error handling."""
        with patch('src.routes.auth.User') as mock_user:
            mock_user.query.filter_by.side_effect = Exception("Database error")
            
            response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    def test_validation_error(self, client):
        """Test validation error handling."""
        response = client.post('/api/v1/auth/register', json={
            'email': 'invalid-email',  # Invalid email format
            'password': '123'  # Too short password
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_unauthorized_access(self, client):
        """Test unauthorized access handling."""
        response = client.get('/api/v1/campaigns')  # No auth header
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
