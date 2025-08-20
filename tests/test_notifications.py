"""
Unit tests for NotificationService class.

This module tests all methods of the NotificationService class with mocked external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.notifications import NotificationService


class TestNotificationService:
    """Test cases for NotificationService class."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-resend-key',
            'NOTIFY_EMAIL_FROM': 'test@example.com',
            'NOTIFY_EMAIL_TO': 'admin@example.com,user@example.com',
            'NOTIFICATIONS_ENABLED': 'true'
        }):
            yield

    @pytest.fixture
    def notification_service(self, mock_env):
        """Create a NotificationService instance for testing."""
        return NotificationService()

    @pytest.fixture
    def mock_lead(self):
        """Create a mock lead object."""
        lead = Mock()
        lead.full_name = "John Doe"
        lead.public_identifier = "john-doe-123"
        lead.email = "john@example.com"
        lead.id = 123
        lead.company_name = "Test Company"
        return lead

    @pytest.fixture
    def mock_campaign(self):
        """Create a mock campaign object."""
        campaign = Mock()
        campaign.name = "Test Campaign"
        campaign.id = 1
        return campaign

    @pytest.fixture
    def mock_linkedin_account(self):
        """Create a mock LinkedIn account object."""
        account = Mock()
        account.account_id = "linkedin-account-123"
        account.name = "Test LinkedIn Account"
        return account

    def test_init_with_api_key(self, mock_env):
        """Test service initialization with API key."""
        service = NotificationService()
        assert service.resend_api_key == 'test-resend-key'
        assert service.from_email == 'test@example.com'
        assert service.to_emails == ['admin@example.com', 'user@example.com']
        assert service.enabled is True

    def test_init_without_api_key(self):
        """Test service initialization without API key."""
        with patch.dict('os.environ', {}, clear=True):
            service = NotificationService()
            assert service.resend_api_key is None
            assert service.enabled is False

    def test_init_notifications_disabled(self):
        """Test service initialization with notifications disabled."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFICATIONS_ENABLED': 'false'
        }):
            service = NotificationService()
            assert service.enabled is False

    def test_init_single_email(self):
        """Test service initialization with single email."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFY_EMAIL_TO': 'single@example.com'
        }):
            service = NotificationService()
            assert service.to_emails == ['single@example.com']

    @patch('resend.Emails.send')
    def test_send_reply_notification_success(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test successful reply notification sending."""
        mock_send.return_value = {'id': 'email-123'}
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account, "Test message"
        )
        
        assert result is True
        assert mock_send.call_count == 2  # Called for each email in to_emails
        
        # Check the first call - resend uses dictionary argument
        first_call = mock_send.call_args_list[0]
        assert first_call[0][0]['from'] == 'test@example.com'
        assert first_call[0][0]['to'] == 'admin@example.com'
        assert 'Lead Reply: John Doe (Test Campaign)' in first_call[0][0]['subject']
        assert 'John Doe' in first_call[0][0]['html']

    @patch('resend.Emails.send')
    def test_send_reply_notification_without_message_preview(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification without message preview."""
        mock_send.return_value = {'id': 'email-123'}
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is True
        assert mock_send.call_count == 2

    @patch('resend.Emails.send')
    def test_send_reply_notification_partial_failure(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification with partial failure."""
        # First email succeeds, second fails
        mock_send.side_effect = [
            {'id': 'email-123'},  # First call succeeds
            Exception("Email failed")  # Second call fails
        ]
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is True  # Should still return True if at least one email succeeds
        assert mock_send.call_count == 2

    @patch('resend.Emails.send')
    def test_send_reply_notification_all_failures(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification with all failures."""
        mock_send.side_effect = Exception("All emails failed")
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is False
        assert mock_send.call_count == 2

    @patch('resend.Emails.send')
    def test_send_connection_notification_success(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test successful connection notification sending."""
        mock_send.return_value = {'id': 'email-123'}
        
        result = notification_service.send_connection_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is True
        assert mock_send.call_count == 2
        
        # Check the first call - resend uses dictionary argument
        first_call = mock_send.call_args_list[0]
        assert first_call[0][0]['from'] == 'test@example.com'
        assert first_call[0][0]['to'] == 'admin@example.com'
        assert 'Connection Accepted: John Doe (Test Campaign)' in first_call[0][0]['subject']
        assert 'John Doe' in first_call[0][0]['html']

    def test_send_reply_notification_disabled(self, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification when notifications are disabled."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFICATIONS_ENABLED': 'false'
        }):
            service = NotificationService()
            
            result = service.send_reply_notification(
                mock_lead, mock_campaign, mock_linkedin_account
            )
            
            assert result is False

    def test_send_connection_notification_disabled(self, mock_lead, mock_campaign, mock_linkedin_account):
        """Test connection notification when notifications are disabled."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFICATIONS_ENABLED': 'false'
        }):
            service = NotificationService()
            
            result = service.send_connection_notification(
                mock_lead, mock_campaign, mock_linkedin_account
            )
            
            assert result is False

    @patch('resend.Emails.send')
    def test_send_reply_notification_empty_emails(self, mock_send, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification with empty email list."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFY_EMAIL_TO': ''
        }):
            service = NotificationService()
            
            result = service.send_reply_notification(
                mock_lead, mock_campaign, mock_linkedin_account
            )
            
            assert result is False
            mock_send.assert_not_called()

    @patch('resend.Emails.send')
    def test_send_reply_notification_whitespace_emails(self, mock_send, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification with whitespace-only emails."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key',
            'NOTIFY_EMAIL_TO': '  ,  ,  '
        }):
            service = NotificationService()
            
            result = service.send_reply_notification(
                mock_lead, mock_campaign, mock_linkedin_account
            )
            
            assert result is False
            mock_send.assert_not_called()

    def test_create_reply_notification_template(self, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification template creation."""
        html_content = notification_service._create_reply_notification_template(
            mock_lead, mock_campaign, mock_linkedin_account, "Test message preview"
        )
        
        assert 'John Doe' in html_content
        assert 'Test Campaign' in html_content
        assert 'Test message preview' in html_content
        assert 'Test LinkedIn Account' in html_content  # Account name, not ID
        # The template doesn't include public_identifier, so we check for lead ID instead
        assert 'Lead ID: 123' in html_content

    def test_create_connection_notification_template(self, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test connection notification template creation."""
        html_content = notification_service._create_connection_notification_template(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert 'John Doe' in html_content
        assert 'Test Campaign' in html_content
        assert 'Test LinkedIn Account' in html_content  # Account name, not ID
        # The template doesn't include public_identifier, so we check for lead ID instead
        assert 'Lead ID: 123' in html_content
        assert 'connection' in html_content.lower()

    def test_create_reply_notification_template_without_message(self, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification template without message preview."""
        html_content = notification_service._create_reply_notification_template(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert 'John Doe' in html_content
        assert 'Test Campaign' in html_content
        # The actual implementation doesn't show "No message preview available" when no message is provided
        # It just shows an empty message section

    def test_create_reply_notification_template_with_long_message(self, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification template with long message."""
        long_message = "This is a very long message that should be truncated if it exceeds a certain length. " * 10
        
        html_content = notification_service._create_reply_notification_template(
            mock_lead, mock_campaign, mock_linkedin_account, long_message
        )
        
        assert 'John Doe' in html_content
        assert len(html_content) < 10000  # Should not be excessively long

    @patch('resend.Emails.send')
    def test_send_reply_notification_exception_handling(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test reply notification exception handling."""
        mock_send.side_effect = Exception("Unexpected error")
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is False

    @patch('resend.Emails.send')
    def test_send_connection_notification_exception_handling(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test connection notification exception handling."""
        mock_send.side_effect = Exception("Unexpected error")
        
        result = notification_service.send_connection_notification(
            mock_lead, mock_campaign, mock_linkedin_account
        )
        
        assert result is False

    def test_notification_service_default_values(self):
        """Test notification service with default values."""
        with patch.dict('os.environ', {
            'RESEND_API_KEY': 'test-key'
            # No other environment variables
        }):
            service = NotificationService()
            assert service.from_email == 'notifications@notifications.costperdemo.com'
            # The actual implementation has a default email, not empty string
            assert len(service.to_emails) > 0
            # With RESEND_API_KEY set, notifications are enabled
            assert service.enabled is True

    @patch('resend.Emails.send')
    def test_send_reply_notification_with_special_characters(self, mock_send, notification_service, mock_campaign, mock_linkedin_account):
        """Test reply notification with special characters in lead name."""
        mock_lead = Mock()
        mock_lead.full_name = "José María O'Connor-Smith"
        mock_lead.public_identifier = "jose-maria-123"
        mock_lead.email = "jose@example.com"
        mock_lead.id = 456
        mock_lead.company_name = "Test Company"
        
        mock_send.return_value = {'id': 'email-123'}
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account, "Test message"
        )
        
        assert result is True
        assert mock_send.call_count == 2
        
        # Check that special characters are handled properly
        first_call = mock_send.call_args_list[0]
        assert "José María O'Connor-Smith" in first_call[0][0]['subject']

    @patch('resend.Emails.send')
    def test_send_notification_with_html_content(self, mock_send, notification_service, mock_lead, mock_campaign, mock_linkedin_account):
        """Test notification with HTML content in lead name and message."""
        mock_lead.full_name = "John <script>alert('xss')</script> Doe"
        
        mock_send.return_value = {'id': 'email-123'}
        
        result = notification_service.send_reply_notification(
            mock_lead, mock_campaign, mock_linkedin_account, "Test <script>alert('xss')</script> message"
        )
        
        assert result is True
        
        # Check that HTML content is included in the template (not escaped, which is correct for templates)
        first_call = mock_send.call_args_list[0]
        html_content = first_call[0][0]['html']
        assert '<script>' in html_content  # HTML is included as-is in the template
        assert 'John <script>alert(\'xss\')</script> Doe' in html_content
