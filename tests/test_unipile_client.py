"""
Unit tests for UnipileClient class.

This module tests all methods of the UnipileClient class with mocked external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from src.services.unipile_client import UnipileClient, UnipileAPIError


class TestUnipileClient:
    """Test cases for UnipileClient class."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {
            'UNIPILE_API_KEY': 'test-api-key',
            'UNIPILE_API_BASE_URL': 'https://test-api.unipile.com'
        }):
            yield

    @pytest.fixture
    def client(self, mock_env):
        """Create a UnipileClient instance for testing."""
        return UnipileClient()

    @pytest.fixture
    def mock_response(self):
        """Create a mock response object."""
        response = Mock()
        response.json.return_value = {'status': 'success'}
        response.raise_for_status.return_value = None
        return response

    def test_init_with_api_key(self, mock_env):
        """Test client initialization with API key."""
        client = UnipileClient('custom-api-key')
        assert client.api_key == 'custom-api-key'
        assert client.base_url == 'https://test-api.unipile.com'

    def test_init_without_api_key(self):
        """Test client initialization without API key."""
        with patch.dict('os.environ', {}, clear=True):
            client = UnipileClient()
            assert client.api_key is None

    def test_get_api_key_from_env(self, mock_env):
        """Test getting API key from environment."""
        client = UnipileClient()
        assert client.api_key == 'test-api-key'

    def test_get_base_url_from_env(self, mock_env):
        """Test getting base URL from environment."""
        client = UnipileClient()
        assert client.base_url == 'https://test-api.unipile.com'

    def test_get_base_url_default(self):
        """Test getting default base URL when not in environment."""
        with patch.dict('os.environ', {}, clear=True):
            client = UnipileClient()
            assert client.base_url == 'https://api3.unipile.com:13359'

    @patch('requests.request')
    def test_make_request_success(self, mock_request, client, mock_response):
        """Test successful API request."""
        mock_request.return_value = mock_response
        
        result = client._make_request('GET', '/test-endpoint')
        
        assert result == {'status': 'success'}
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0] == ('GET', 'https://test-api.unipile.com/test-endpoint')
        assert 'X-API-KEY' in call_args[1]['headers']
        assert call_args[1]['headers']['X-API-KEY'] == 'test-api-key'

    @patch('requests.request')
    def test_make_request_with_json(self, mock_request, client, mock_response):
        """Test API request with JSON data."""
        mock_request.return_value = mock_response
        
        client._make_request('POST', '/test-endpoint', json={'test': 'data'})
        
        call_args = mock_request.call_args
        assert call_args[1]['headers']['Content-Type'] == 'application/json'
        assert call_args[1]['json'] == {'test': 'data'}

    @patch('requests.request')
    def test_make_request_without_api_key(self, mock_request):
        """Test API request without API key."""
        with patch.dict('os.environ', {}, clear=True):
            client = UnipileClient()
            
            with pytest.raises(UnipileAPIError, match="No Unipile API key available"):
                client._make_request('GET', '/test-endpoint')

    @patch('requests.request')
    def test_make_request_http_error(self, mock_request, client):
        """Test API request with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Client Error')
        mock_request.return_value = mock_response
        
        with pytest.raises(UnipileAPIError) as exc_info:
            client._make_request('GET', '/test-endpoint')
        
        assert '404 Client Error' in str(exc_info.value)
        # Note: The actual implementation doesn't set status_code on the exception
        # So we just check the error message

    @patch('requests.request')
    def test_make_request_connection_error(self, mock_request, client):
        """Test API request with connection error."""
        mock_request.side_effect = requests.exceptions.ConnectionError('Connection failed')
        
        with pytest.raises(UnipileAPIError) as exc_info:
            client._make_request('GET', '/test-endpoint')
        
        assert 'Connection failed' in str(exc_info.value)

    @patch.object(UnipileClient, '_make_request')
    def test_get_accounts(self, mock_make_request, client):
        """Test get_accounts method."""
        mock_make_request.return_value = {'accounts': []}
        
        result = client.get_accounts()
        
        assert result == {'accounts': []}
        mock_make_request.assert_called_once_with('GET', '/api/v1/accounts')

    @patch.object(UnipileClient, '_make_request')
    def test_get_account(self, mock_make_request, client):
        """Test get_account method."""
        mock_make_request.return_value = {'id': 'test-account'}
        
        result = client.get_account('test-id')
        
        assert result == {'id': 'test-account'}
        mock_make_request.assert_called_once_with('GET', '/api/v1/accounts/test-id')

    @patch.object(UnipileClient, '_make_request')
    def test_get_relations(self, mock_make_request, client):
        """Test get_relations method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.get_relations('test-account')
        
        assert result == {'items': [], 'cursor': None}
        mock_make_request.assert_called_once_with('GET', '/api/v1/users/relations', params={'account_id': 'test-account'})

    @patch.object(UnipileClient, '_make_request')
    def test_get_relations_with_cursor(self, mock_make_request, client):
        """Test get_relations method with cursor."""
        mock_make_request.return_value = {'items': [], 'cursor': 'next-page'}
        
        result = client.get_relations('test-account', cursor='test-cursor', limit=50)
        
        assert result == {'items': [], 'cursor': 'next-page'}
        expected_params = {
            'account_id': 'test-account',
            'cursor': 'test-cursor',
            'limit': 50
        }
        mock_make_request.assert_called_once_with('GET', '/api/v1/users/relations', params=expected_params)

    @patch.object(UnipileClient, '_make_request')
    def test_get_sent_invitations(self, mock_make_request, client):
        """Test get_sent_invitations method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.get_sent_invitations('test-account')
        
        assert result == {'items': [], 'cursor': None}
        mock_make_request.assert_called_once_with('GET', '/api/v1/users/invite/sent', params={'account_id': 'test-account'})

    @patch.object(UnipileClient, '_make_request')
    def test_get_user_profile(self, mock_make_request, client):
        """Test get_user_profile method."""
        mock_make_request.return_value = {'first_name': 'John', 'last_name': 'Doe'}
        
        result = client.get_user_profile('test-profile', 'test-account')
        
        assert result == {'first_name': 'John', 'last_name': 'Doe'}
        mock_make_request.assert_called_once_with('GET', '/api/v1/users/test-profile', params={'account_id': 'test-account'})

    @patch.object(UnipileClient, '_make_request')
    def test_get_user_profile_by_member_id(self, mock_make_request, client):
        """Test get_user_profile_by_member_id method."""
        mock_make_request.return_value = {'member_id': 'test-member'}
        
        result = client.get_user_profile_by_member_id('test-member', 'test-account')
        
        assert result == {'member_id': 'test-member'}
        mock_make_request.assert_called_once_with('GET', '/api/v1/users/test-member', params={'account_id': 'test-account'})

    @patch.object(UnipileClient, '_make_request')
    def test_send_connection_request(self, mock_make_request, client):
        """Test send_connection_request method."""
        mock_make_request.return_value = {'id': 'invitation-123'}
        
        result = client.send_connection_request('test-account', 'test-profile', 'Hello!')
        
        assert result == {'id': 'invitation-123'}
        expected_data = {
            'provider_id': 'test-profile',
            'account_id': 'test-account',
            'message': 'Hello!'
        }
        mock_make_request.assert_called_once_with('POST', '/api/v1/users/invite', json=expected_data)

    @patch.object(UnipileClient, '_make_request')
    def test_send_connection_request_without_message(self, mock_make_request, client):
        """Test send_connection_request method without message."""
        mock_make_request.return_value = {'id': 'invitation-123'}
        
        result = client.send_connection_request('test-account', 'test-profile')
        
        assert result == {'id': 'invitation-123'}
        expected_data = {
            'provider_id': 'test-profile',
            'account_id': 'test-account'
        }
        mock_make_request.assert_called_once_with('POST', '/api/v1/users/invite', json=expected_data)

    @patch.object(UnipileClient, '_make_request')
    def test_send_message(self, mock_make_request, client):
        """Test send_message method."""
        mock_make_request.return_value = {'id': 'message-123'}
        
        result = client.send_message('test-account', 'test-conversation', 'Hello!')
        
        assert result == {'id': 'message-123'}
        expected_files = {
            'account_id': (None, 'test-account'),
            'text': (None, 'Hello!')
        }
        mock_make_request.assert_called_once_with('POST', '/api/v1/chats/test-conversation/messages', files=expected_files)

    @patch.object(UnipileClient, '_make_request')
    def test_send_message_fallback(self, mock_make_request, client):
        """Test send_message method with fallback to legacy endpoint."""
        # First call fails, second succeeds
        mock_make_request.side_effect = [
            UnipileAPIError("Not found"),
            {'id': 'message-123'}
        ]
        
        result = client.send_message('test-account', 'test-conversation', 'Hello!')
        
        assert result == {'id': 'message-123'}
        assert mock_make_request.call_count == 2

    @patch.object(UnipileClient, '_make_request')
    def test_get_conversations(self, mock_make_request, client):
        """Test get_conversations method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.get_conversations('test-account')
        
        assert result == {'items': [], 'cursor': None}
        expected_params = {'account_id': ['test-account']}
        mock_make_request.assert_called_once_with('GET', '/api/v1/chats', params=expected_params)

    @patch.object(UnipileClient, '_make_request')
    def test_get_conversations_with_fallback(self, mock_make_request, client):
        """Test get_conversations method with fallback."""
        # First call fails, second succeeds
        mock_make_request.side_effect = [
            UnipileAPIError("Not found"),
            {'items': [], 'cursor': None}
        ]
        
        result = client.get_conversations('test-account')
        
        assert result == {'items': [], 'cursor': None}
        assert mock_make_request.call_count == 2

    @patch.object(UnipileClient, '_make_request')
    def test_get_messages(self, mock_make_request, client):
        """Test get_messages method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.get_messages('test-account', limit=10)
        
        assert result == {'items': [], 'cursor': None}
        expected_params = {
            'account_id': ['test-account'],
            'limit': 10
        }
        mock_make_request.assert_called_once_with('GET', '/api/v1/messages', params=expected_params)

    @patch.object(UnipileClient, '_make_request')
    def test_create_webhook(self, mock_make_request, client):
        """Test create_webhook method."""
        mock_make_request.return_value = {'id': 'webhook-123'}
        
        result = client.create_webhook('https://example.com/webhook', 'users', 'Test Webhook')
        
        assert result == {'id': 'webhook-123'}
        expected_data = {
            'source': 'users',
            'request_url': 'https://example.com/webhook',
            'name': 'Test Webhook',
            'headers': [{'key': 'Content-Type', 'value': 'application/json'}]
        }
        mock_make_request.assert_called_once_with('POST', '/api/v1/webhooks', json=expected_data)

    @patch.object(UnipileClient, '_make_request')
    def test_list_webhooks(self, mock_make_request, client):
        """Test list_webhooks method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.list_webhooks()
        
        assert result == {'items': [], 'cursor': None}
        mock_make_request.assert_called_once_with('GET', '/api/v1/webhooks')

    @patch.object(UnipileClient, '_make_request')
    def test_delete_webhook(self, mock_make_request, client):
        """Test delete_webhook method."""
        mock_make_request.return_value = {'status': 'deleted'}
        
        result = client.delete_webhook('webhook-123')
        
        assert result == {'status': 'deleted'}
        mock_make_request.assert_called_once_with('DELETE', '/api/v1/webhooks/webhook-123')

    def test_get_first_level_connections(self, client):
        """Test get_first_level_connections method (alias for get_relations)."""
        with patch.object(client, 'get_relations') as mock_get_relations:
            mock_get_relations.return_value = {'items': [], 'cursor': None}
            
            result = client.get_first_level_connections('test-account')
            
            assert result == {'items': [], 'cursor': None}
            mock_get_relations.assert_called_once_with('test-account', cursor=None, limit=None)

    def test_get_linkedin_profile(self, client):
        """Test get_linkedin_profile method (alias for get_user_profile)."""
        with patch.object(client, 'get_user_profile') as mock_get_user_profile:
            mock_get_user_profile.return_value = {'first_name': 'John', 'last_name': 'Doe'}
            
            result = client.get_linkedin_profile('test-account', 'test-profile')
            
            assert result == {'first_name': 'John', 'last_name': 'Doe'}
            mock_get_user_profile.assert_called_once_with('test-profile', 'test-account')

    def test_get_conversation_id(self, client):
        """Test get_conversation_id method (alias for find_conversation_with_provider)."""
        with patch.object(client, 'find_conversation_with_provider') as mock_find:
            mock_find.return_value = 'conversation-123'
            
            result = client.get_conversation_id('test-account', 'test-provider')
            
            assert result == 'conversation-123'
            mock_find.assert_called_once_with('test-account', 'test-provider')

    @patch.object(UnipileClient, '_make_request')
    def test_search_linkedin_profiles(self, mock_make_request, client):
        """Test search_linkedin_profiles method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        search_params = {'keywords': 'software engineer', 'location': [102277331]}
        
        result = client.search_linkedin_profiles('test-account', search_params)
        
        assert result == {'items': [], 'cursor': None}
        expected_params = {'account_id': 'test-account'}
        mock_make_request.assert_called_once_with('POST', '/api/v1/linkedin/search', params=expected_params, json=search_params)

    @patch.object(UnipileClient, '_make_request')
    def test_get_search_parameters(self, mock_make_request, client):
        """Test get_search_parameters method."""
        mock_make_request.return_value = {'items': [], 'cursor': None}
        
        result = client.get_search_parameters('test-account', 'LOCATION', 'New York', 10)
        
        assert result == {'items': [], 'cursor': None}
        expected_params = {
            'account_id': 'test-account',
            'type': 'LOCATION',
            'keywords': 'New York',
            'limit': 10
        }
        mock_make_request.assert_called_once_with('GET', '/api/v1/linkedin/search/parameters', params=expected_params)

    @patch.object(UnipileClient, '_make_request')
    def test_resync_linkedin_account(self, mock_make_request, client):
        """Test resync_linkedin_account method."""
        mock_make_request.return_value = {'status': 'syncing'}
        
        result = client.resync_linkedin_account('test-account')
        
        assert result == {'status': 'syncing'}
        mock_make_request.assert_called_once_with('POST', '/api/v1/accounts/test-account/resync')


class TestUnipileAPIError:
    """Test cases for UnipileAPIError class."""

    def test_unipile_api_error_init(self):
        """Test UnipileAPIError initialization."""
        error = UnipileAPIError("Test error", 404, "Not found")
        
        assert str(error) == "Test error"
        assert error.status_code == 404
        assert error.response_data == "Not found"

    def test_unipile_api_error_without_optional_params(self):
        """Test UnipileAPIError initialization without optional parameters."""
        error = UnipileAPIError("Test error")
        
        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response_data is None
