import os
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

class UnipileAPIError(Exception):
    """Custom exception for Unipile API errors."""
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class UnipileClient:
    """Client for interacting with the Unipile API."""
    
    def __init__(self, api_key=None):
        """Initialize the Unipile client."""
        self.api_key = api_key or self._get_api_key()
        self.base_url = self._get_base_url()
        
        if not self.api_key:
            logger.warning("No Unipile API key provided")
    
    def _get_api_key(self):
        """Get API key from environment or Flask config."""
        # Try environment variable first
        api_key = os.environ.get('UNIPILE_API_KEY')
        if api_key:
            return api_key
        
        # Try Flask config if available
        try:
            if current_app:
                return current_app.config.get('UNIPILE_API_KEY')
        except RuntimeError:
            # No application context
            pass
        
        return None
    
    def _get_base_url(self):
        """Get base URL from environment or Flask config."""
        # Try environment variable first
        base_url = os.environ.get('UNIPILE_API_BASE_URL')
        if base_url:
            return base_url
        
        # Try Flask config if available
        try:
            if current_app:
                return current_app.config.get('UNIPILE_API_BASE_URL', 'https://api.unipile.com/v1')
        except RuntimeError:
            # No application context
            pass
        
        return 'https://api.unipile.com/v1'
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make a request to the Unipile API."""
        if not self.api_key:
            raise UnipileAPIError("No Unipile API key available")
        
        url = f"{self.base_url}{endpoint}"
        # Base headers always include API key; Content-Type only when sending JSON
        headers = {
            'X-API-KEY': self.api_key,
        }
        # Only set JSON content type if using JSON body; allow requests to set for form/multipart
        if 'json' in kwargs and kwargs['json'] is not None:
            headers['Content-Type'] = 'application/json'
        
        # Add headers to kwargs
        if 'headers' in kwargs and kwargs['headers']:
            # Ensure we do not overwrite an explicit Content-Type for multipart/form-data
            merged = {**headers, **kwargs['headers']}
            kwargs['headers'] = merged
        else:
            kwargs['headers'] = headers
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Unipile API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise UnipileAPIError(
                    f"Unipile API request failed: {str(e)}", 
                    status_code=e.response.status_code,
                    response_data=e.response.text
                )
            raise UnipileAPIError(f"Unipile API request failed: {str(e)}")
    
    def get_accounts(self):
        """Get all LinkedIn accounts."""
        return self._make_request('GET', '/api/v1/accounts')
    
    def get_account(self, account_id):
        """Get a specific LinkedIn account."""
        return self._make_request('GET', f'/api/v1/accounts/{account_id}')
    
    def search_people(self, search_config):
        """Search for people on LinkedIn."""
        return self._make_request('POST', '/linkedin/search', json=search_config)
    
    def search_linkedin_profiles(self, account_id, search_params):
        """
        Search for LinkedIn profiles using Sales Navigator or Classic.
        This uses the Unipile API endpoint:
        POST /api/v1/linkedin/search?account_id=... with all search parameters in the JSON body.
        """
        # Remove account_id from the body if present
        search_params = dict(search_params)  # shallow copy
        search_params.pop('account_id', None)
        params = {'account_id': account_id}
        return self._make_request(
            'POST',
            '/api/v1/linkedin/search',
            params=params,
            json=search_params
        )
    
    def search_linkedin_advanced(self, account_id, search_config):
        """
        Search for LinkedIn profiles using advanced search parameters.
        This uses the Unipile API endpoint:
        POST /api/v1/linkedin/search?account_id=... with all search parameters in the JSON body.
        """
        # Remove account_id from the body if present
        search_config = dict(search_config)  # shallow copy
        search_config.pop('account_id', None)
        
        # Extract cursor and limit for query parameters
        cursor = search_config.pop('cursor', None)
        limit = search_config.pop('limit', None)
        
        params = {'account_id': account_id}
        if cursor:
            params['cursor'] = cursor
        if limit:
            params['limit'] = limit
            
        return self._make_request(
            'POST',
            '/api/v1/linkedin/search',
            params=params,
            json=search_config
        )
    
    def get_search_parameters(self, account_id, param_type='LOCATION', keywords=None, limit=100):
        """Get search parameters (locations, industries, skills, etc.).
        Docs: GET /api/v1/linkedin/search/parameters?account_id=...&type=...&keywords=...&limit=...
        """
        params = {
            'account_id': account_id,
            'type': param_type,
            'limit': limit
        }
        if keywords:
            params['keywords'] = keywords
        
        return self._make_request('GET', '/api/v1/linkedin/search/parameters', params=params)
    
    def get_user_profile(self, identifier, account_id):
        """Get a user profile by identifier (public_id or provider_id)."""
        params = {'account_id': account_id}
        return self._make_request('GET', f'/api/v1/users/{identifier}', params=params)
    
    def get_user_profile_by_member_id(self, member_id, account_id):
        """
        Get a user profile by member_id.
        
        Args:
            member_id: The LinkedIn member ID
            account_id: The LinkedIn account ID
            
        Returns:
            dict: User profile data
        """
        endpoint = f"/api/v1/users/{member_id}"
        params = {'account_id': account_id}
        return self._make_request("GET", endpoint, params=params)
    
    def send_connection_request(self, account_id, profile_id, message=None):
        """Send a connection request using the correct Unipile API flow."""
        data = {
            'provider_id': profile_id,
            'account_id': account_id
        }
        if message:
            data['message'] = message
        
        return self._make_request('POST', '/api/v1/users/invite', json=data)
    
    def send_message(self, account_id, conversation_id, message):
        """Send a message to a conversation.
        Docs primary: POST /api/v1/chats/{chat_id}/messages (multipart form) with field `text`.
        """
        files = {
            'text': (None, message)
        }
        alt_endpoint = f"/api/v1/chats/{conversation_id}/messages"
        try:
            return self._make_request("POST", alt_endpoint, files=files)
        except UnipileAPIError:
            # Fallback to legacy JSON endpoint if chats API not available
            data = {"message": message}
            endpoint = f"/api/v1/linkedin/accounts/{account_id}/conversations/{conversation_id}/messages"
            return self._make_request("POST", endpoint, json=data)
    
    def get_conversations(self, account_id):
        """Get conversations (chats) for an account (with fallbacks)."""
        # Doc references: GET /api/v1/chats?account_id=...
        try:
            return self._make_request("GET", "/api/v1/chats", params={"account_id": account_id})
        except UnipileAPIError:
            # Fallback legacy endpoints
            try:
                return self._make_request("GET", f"/api/v1/linkedin/accounts/{account_id}/conversations")
            except UnipileAPIError:
                return self._make_request("GET", "/api/v1/conversations", params={"account_id": account_id})

    def find_conversation_with_provider(self, account_id, provider_id):
        """Find a chat that includes the given participant provider_id.
        Returns the Unipile chat_id (which we can use for /chats/{chat_id}/messages)."""
        convs = self.get_conversations(account_id)
        # Chats list can be { items: [...] } or a list
        items = convs.get("items", convs if isinstance(convs, list) else [])
        for chat in items:
            # Unipile chat participants may appear under attendees or participants
            participants = chat.get("participants") or chat.get("attendees") or []
            for p in participants:
                if p.get("provider_id") == provider_id or p.get("attendee_provider_id") == provider_id:
                    # Prefer Unipile chat id field: id or chat_id
                    return chat.get("id") or chat.get("chat_id")
        return None

    def start_chat_with_attendee(self, account_id, attendee_provider_id, text):
        """Start a 1:1 chat (or reuse existing) and send an initial message using /api/v1/chats.
        This uses multipart/form-data per docs. `attendees_ids` expects LinkedIn member_id when possible.
        """
        files = {
            'account_id': (None, account_id),
            'attendees_ids': (None, attendee_provider_id),
            'text': (None, text),
            'linkedin[api]': (None, 'classic'),
        }
        return self._make_request("POST", "/api/v1/chats", files=files)
    
    def get_conversation(self, account_id, conversation_id):
        """Get a specific conversation."""
        return self._make_request('GET', f'/api/v1/linkedin/accounts/{account_id}/conversations/{conversation_id}')
    
    def get_profile(self, account_id, profile_id):
        """Get a LinkedIn profile."""
        return self._make_request('GET', f'/api/v1/linkedin/accounts/{account_id}/profiles/{profile_id}')
    
    def get_invitations(self, account_id):
        """Get pending invitations for an account."""
        return self._make_request('GET', f'/api/v1/linkedin/accounts/{account_id}/invitations')
    
    def accept_invitation(self, account_id, invitation_id):
        """Accept a connection invitation."""
        return self._make_request('POST', f'/api/v1/linkedin/accounts/{account_id}/invitations/{invitation_id}/accept')
    
    def reject_invitation(self, account_id, invitation_id):
        """Reject a connection invitation."""
        return self._make_request('POST', f'/api/v1/linkedin/accounts/{account_id}/invitations/{invitation_id}/reject')

    def create_webhook(self, request_url, webhook_type="users", name="LinkedIn Connection Monitor"):
        """
        Create a webhook for monitoring LinkedIn connections.
        
        Args:
            request_url: The URL where Unipile should send webhook events
            webhook_type: "users" for connection events, "messaging" for messages
            name: Name for the webhook
            
        Returns:
            dict: Webhook creation response
        """
        endpoint = "/api/v1/webhooks"
        
        data = {
            "source": webhook_type,
            "request_url": request_url,
            "name": name,
            "headers": [
                {
                    "key": "Content-Type",
                    "value": "application/json"
                }
            ]
        }
        
        return self._make_request("POST", endpoint, json=data)

    def list_webhooks(self):
        """
        List all webhooks for the account.
        
        Returns:
            dict: List of webhooks
        """
        endpoint = "/api/v1/webhooks"
        return self._make_request("GET", endpoint)

    def delete_webhook(self, webhook_id):
        """
        Delete a webhook.
        
        Args:
            webhook_id: The ID of the webhook to delete
            
        Returns:
            dict: Deletion response
        """
        endpoint = f"/api/v1/webhooks/{webhook_id}"
        return self._make_request("DELETE", endpoint)

    def get_relations(self, account_id, cursor=None, limit=None):
        """
        Get relations (connections) for a LinkedIn account (paginated).
        
        Args:
            account_id: The LinkedIn account ID
            cursor: Optional pagination cursor
            limit: Optional page size (1..1000)
        Returns:
            dict: { items: [...], cursor: "..." }
        """
        endpoint = "/api/v1/users/relations"
        params = {'account_id': account_id}
        if cursor:
            params['cursor'] = cursor
        if limit:
            params['limit'] = limit
        return self._make_request("GET", endpoint, params=params)

    def get_sent_invitations(self, account_id):
        """
        Get all sent invitations for a LinkedIn account.
        
        Args:
            account_id: The LinkedIn account ID
            
        Returns:
            dict: List of sent invitations
        """
        endpoint = f"/api/v1/linkedin/accounts/{account_id}/invitations"
        return self._make_request("GET", endpoint)

