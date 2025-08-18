"""
Integration tests for API endpoints.

This module tests:
- API endpoint functionality
- Request/response formats
- Error handling
- Authentication (when implemented)
"""

import pytest
import json
from datetime import datetime

from src.models import Client, Campaign, Lead, Event


@pytest.mark.integration
class TestClientEndpoints:
    """Test client-related API endpoints."""
    
    def test_get_clients(self, client, sample_client):
        """Test GET /api/v1/clients endpoint."""
        response = client.get('/api/v1/clients')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'clients' in data
        assert len(data['clients']) >= 1
        
        # Check that our sample client is in the response
        client_ids = [c['id'] for c in data['clients']]
        assert sample_client.id in client_ids
    
    def test_get_clients_with_campaigns(self, client, sample_client, sample_campaign):
        """Test GET /api/v1/clients?include_campaigns=true endpoint."""
        response = client.get('/api/v1/clients?include_campaigns=true')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'clients' in data
        
        # Find our sample client
        test_client = None
        for c in data['clients']:
            if c['id'] == sample_client.id:
                test_client = c
                break
        
        assert test_client is not None
        assert 'campaigns' in test_client
        assert len(test_client['campaigns']) == 1
        assert test_client['campaigns'][0]['id'] == sample_campaign.id
    
    def test_get_client_by_id(self, client, sample_client):
        """Test GET /api/v1/clients/<client_id> endpoint."""
        response = client.get(f'/api/v1/clients/{sample_client.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'client' in data
        assert data['client']['id'] == sample_client.id
        assert data['client']['name'] == sample_client.name
    
    def test_get_client_not_found(self, client):
        """Test GET /api/v1/clients/<invalid_id> endpoint."""
        response = client.get('/api/v1/clients/nonexistent-id')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'
    
    def test_create_client(self, client):
        """Test POST /api/v1/clients endpoint."""
        client_data = {
            'name': 'New Test Client',
            'email': 'newtest@example.com'
        }
        
        response = client.post(
            '/api/v1/clients',
            data=json.dumps(client_data),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data
        assert 'client' in data
        assert data['client']['name'] == 'New Test Client'
        assert data['client']['email'] == 'newtest@example.com'
    
    def test_create_client_missing_name(self, client):
        """Test POST /api/v1/clients with missing required field."""
        client_data = {
            'email': 'newtest@example.com'
        }
        
        response = client.post(
            '/api/v1/clients',
            data=json.dumps(client_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert 'name' in data['error']['message']
    
    def test_update_client(self, client, sample_client):
        """Test PUT /api/v1/clients/<client_id> endpoint."""
        update_data = {
            'name': 'Updated Client Name',
            'email': 'updated@example.com'
        }
        
        response = client.put(
            f'/api/v1/clients/{sample_client.id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data
        assert 'client' in data
        assert data['client']['name'] == 'Updated Client Name'
        assert data['client']['email'] == 'updated@example.com'
    
    def test_update_client_not_found(self, client):
        """Test PUT /api/v1/clients/<invalid_id> endpoint."""
        update_data = {'name': 'Updated Name'}
        
        response = client.put(
            '/api/v1/clients/nonexistent-id',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'


class TestCampaignEndpoints:
    """Test campaign-related API endpoints."""
    
    def test_get_campaigns(self, client, sample_campaign):
        """Test GET /api/v1/campaigns endpoint."""
        response = client.get('/api/v1/campaigns')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'campaigns' in data
        assert len(data['campaigns']) >= 1
        
        # Check that our sample campaign is in the response
        campaign_ids = [c['id'] for c in data['campaigns']]
        assert sample_campaign.id in campaign_ids
    
    def test_get_campaigns_filtered_by_client(self, client, sample_client, sample_campaign):
        """Test GET /api/v1/campaigns?client_id=<client_id> endpoint."""
        response = client.get(f'/api/v1/campaigns?client_id={sample_client.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'campaigns' in data
        assert len(data['campaigns']) == 1
        assert data['campaigns'][0]['id'] == sample_campaign.id
    
    def test_get_campaigns_invalid_client(self, client):
        """Test GET /api/v1/campaigns with invalid client_id."""
        response = client.get('/api/v1/campaigns?client_id=nonexistent-client')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'
    
    def test_create_campaign(self, client, sample_client):
        """Test POST /api/v1/clients/<client_id>/campaigns endpoint."""
        campaign_data = {
            'name': 'New Test Campaign',
            'timezone': 'UTC',
            'status': 'draft',
            'sequence_json': [
                {
                    'type': 'message',
                    'content': 'Hello {{first_name}}!',
                    'delay_days': 1
                }
            ]
        }
        
        response = client.post(
            f'/api/v1/clients/{sample_client.id}/campaigns',
            data=json.dumps(campaign_data),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data
        assert 'campaign' in data
        assert data['campaign']['name'] == 'New Test Campaign'
        assert data['campaign']['timezone'] == 'UTC'
        assert data['campaign']['status'] == 'draft'
    
    def test_create_campaign_missing_name(self, client, sample_client):
        """Test POST /api/v1/clients/<client_id>/campaigns with missing required field."""
        campaign_data = {
            'timezone': 'UTC',
            'status': 'draft'
        }
        
        response = client.post(
            f'/api/v1/clients/{sample_client.id}/campaigns',
            data=json.dumps(campaign_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'VALIDATION_ERROR'


class TestLeadEndpoints:
    """Test lead-related API endpoints."""
    
    def test_get_leads(self, client, sample_campaign, sample_lead):
        """Test GET /api/v1/campaigns/<campaign_id>/leads endpoint."""
        response = client.get(f'/api/v1/campaigns/{sample_campaign.id}/leads')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'leads' in data
        assert len(data['leads']) >= 1
        
        # Check that our sample lead is in the response
        lead_ids = [l['id'] for l in data['leads']]
        assert sample_lead.id in lead_ids
    
    def test_get_leads_campaign_not_found(self, client):
        """Test GET /api/v1/campaigns/<invalid_id>/leads endpoint."""
        response = client.get('/api/v1/campaigns/nonexistent-id/leads')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'
    
    def test_create_lead(self, client, sample_campaign):
        """Test POST /api/v1/campaigns/<campaign_id>/leads endpoint."""
        lead_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'company_name': 'Test Company',
            'public_identifier': 'jane-smith-456',
            'provider_id': 'provider-456',
            'status': 'pending_invite'
        }
        
        response = client.post(
            f'/api/v1/campaigns/{sample_campaign.id}/leads',
            data=json.dumps(lead_data),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data
        assert 'lead' in data
        assert data['lead']['first_name'] == 'Jane'
        assert data['lead']['last_name'] == 'Smith'
        assert data['lead']['public_identifier'] == 'jane-smith-456'
    
    def test_create_lead_missing_public_identifier(self, client, sample_campaign):
        """Test POST /api/v1/campaigns/<campaign_id>/leads with missing required field."""
        lead_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'company_name': 'Test Company'
        }
        
        response = client.post(
            f'/api/v1/campaigns/{sample_campaign.id}/leads',
            data=json.dumps(lead_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert 'public_identifier' in data['error']['message']


class TestErrorHandling:
    """Test error handling across endpoints."""
    
    def test_404_not_found(self, client):
        """Test 404 error handling for non-existent endpoints."""
        response = client.get('/api/v1/nonexistent-endpoint')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'
        assert 'message' in data['error']
    
    def test_405_method_not_allowed(self, client):
        """Test 405 error handling for unsupported methods."""
        response = client.put('/api/v1/clients')
        
        assert response.status_code == 405
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'BAD_REQUEST'
    
    def test_400_bad_request(self, client):
        """Test 400 error handling for malformed requests."""
        response = client.post(
            '/api/v1/clients',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_root_health_check(self, client):
        """Test GET / endpoint."""
        response = client.get('/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data
        assert data['status'] == 'ok'
        assert 'message' in data
    
    def test_webhook_health(self, client):
        """Test GET /api/v1/webhooks/webhook/health endpoint."""
        response = client.get('/api/v1/webhooks/webhook/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data
        assert data['status'] == 'healthy'
        assert 'database' in data
        assert data['database'] == 'connected'
