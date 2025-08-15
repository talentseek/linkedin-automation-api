import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import resend
from flask import current_app

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending email notifications via Resend."""
    
    def __init__(self):
        self.resend_api_key = os.environ.get('RESEND_API_KEY')
        self.from_email = os.environ.get('NOTIFY_EMAIL_FROM', 'notifications@linkedin-automation.com')
        self.to_emails = os.environ.get('NOTIFY_EMAIL_TO', '').split(',')
        self.enabled = os.environ.get('NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
        
        if self.resend_api_key:
            resend.api_key = self.resend_api_key
            logger.info("Resend API key configured")
        else:
            logger.warning("No Resend API key found - notifications will be disabled")
            self.enabled = False
    
    def send_reply_notification(self, lead, campaign, linkedin_account, message_preview: Optional[str] = None) -> bool:
        """Send notification when a lead replies."""
        if not self.enabled:
            logger.info("Notifications disabled - skipping reply notification")
            return False
        
        try:
            subject = f"🔔 Lead Reply: {lead.full_name} ({campaign.name})"
            
            # Create a professional email template
            html_content = self._create_reply_notification_template(
                lead=lead,
                campaign=campaign,
                linkedin_account=linkedin_account,
                message_preview=message_preview
            )
            
            # Send to all configured email addresses
            success_count = 0
            for email in self.to_emails:
                email = email.strip()
                if email:
                    try:
                        response = resend.Emails.send({
                            "from": self.from_email,
                            "to": email,
                            "subject": subject,
                            "html": html_content
                        })
                        logger.info(f"Reply notification sent to {email}: {response.get('id')}")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send notification to {email}: {str(e)}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending reply notification: {str(e)}")
            return False
    
    def send_connection_notification(self, lead, campaign, linkedin_account) -> bool:
        """Send notification when a lead accepts connection."""
        if not self.enabled:
            logger.info("Notifications disabled - skipping connection notification")
            return False
        
        try:
            subject = f"🤝 Connection Accepted: {lead.full_name} ({campaign.name})"
            
            html_content = self._create_connection_notification_template(
                lead=lead,
                campaign=campaign,
                linkedin_account=linkedin_account
            )
            
            success_count = 0
            for email in self.to_emails:
                email = email.strip()
                if email:
                    try:
                        response = resend.Emails.send({
                            "from": self.from_email,
                            "to": email,
                            "subject": subject,
                            "html": html_content
                        })
                        logger.info(f"Connection notification sent to {email}: {response.get('id')}")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send connection notification to {email}: {str(e)}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending connection notification: {str(e)}")
            return False
    
    def send_error_notification(self, error_type: str, error_message: str, context: Dict[str, Any] = None) -> bool:
        """Send notification for system errors."""
        if not self.enabled:
            logger.info("Notifications disabled - skipping error notification")
            return False
        
        try:
            subject = f"⚠️ System Error: {error_type}"
            
            html_content = self._create_error_notification_template(
                error_type=error_type,
                error_message=error_message,
                context=context
            )
            
            success_count = 0
            for email in self.to_emails:
                email = email.strip()
                if email:
                    try:
                        response = resend.Emails.send({
                            "from": self.from_email,
                            "to": email,
                            "subject": subject,
                            "html": html_content
                        })
                        logger.info(f"Error notification sent to {email}: {response.get('id')}")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send error notification to {email}: {str(e)}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending error notification: {str(e)}")
            return False
    
    def _create_reply_notification_template(self, lead, campaign, linkedin_account, message_preview: Optional[str] = None) -> str:
        """Create HTML template for reply notifications."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #0077b5; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .highlight {{ background: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3; margin: 15px 0; }}
                .button {{ display: inline-block; background: #0077b5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 Lead Reply Received</h1>
                    <p>Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
                
                <div class="content">
                    <h2>Lead Details</h2>
                    <div class="highlight">
                        <strong>Name:</strong> {lead.full_name}<br>
                        <strong>Company:</strong> {lead.company_name or 'Not specified'}<br>
                        <strong>Campaign:</strong> {campaign.name}<br>
                        <strong>LinkedIn Account:</strong> {linkedin_account.name or linkedin_account.account_id}
                    </div>
                    
                    {f'<h3>Message Preview</h3><div class="highlight">{message_preview[:200]}{"..." if len(message_preview) > 200 else ""}</div>' if message_preview else ''}
                    
                    <h3>Next Steps</h3>
                    <p>This lead has replied and automation has been stopped. Please:</p>
                    <ol>
                        <li>Log into LinkedIn using the account: <strong>{linkedin_account.name or linkedin_account.account_id}</strong></li>
                        <li>Find the conversation with <strong>{lead.full_name}</strong></li>
                        <li>Respond appropriately to maintain the relationship</li>
                    </ol>
                    
                    <p><strong>Note:</strong> This lead will no longer receive automated messages from this campaign.</p>
                </div>
                
                <div class="footer">
                    <p>This notification was sent by LinkedIn Automation API</p>
                    <p>Campaign ID: {campaign.id} | Lead ID: {lead.id}</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_connection_notification_template(self, lead, campaign, linkedin_account) -> str:
        """Create HTML template for connection notifications."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #28a745; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .highlight {{ background: #e8f5e8; padding: 15px; border-left: 4px solid #28a745; margin: 15px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤝 Connection Accepted</h1>
                    <p>Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
                
                <div class="content">
                    <h2>Connection Details</h2>
                    <div class="highlight">
                        <strong>Lead:</strong> {lead.full_name}<br>
                        <strong>Company:</strong> {lead.company_name or 'Not specified'}<br>
                        <strong>Campaign:</strong> {campaign.name}<br>
                        <strong>LinkedIn Account:</strong> {linkedin_account.name or linkedin_account.account_id}
                    </div>
                    
                    <h3>What Happens Next</h3>
                    <p>This lead has accepted the connection request. The automation will:</p>
                    <ul>
                        <li>Send the first follow-up message according to the campaign sequence</li>
                        <li>Continue with the automated outreach process</li>
                        <li>Monitor for replies and stop automation if a reply is received</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This notification was sent by LinkedIn Automation API</p>
                    <p>Campaign ID: {campaign.id} | Lead ID: {lead.id}</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_error_notification_template(self, error_type: str, error_message: str, context: Dict[str, Any] = None) -> str:
        """Create HTML template for error notifications."""
        context_html = ""
        if context:
            context_html = "<h3>Context</h3><div class='highlight'><pre>" + str(context) + "</pre></div>"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .highlight {{ background: #ffe6e6; padding: 15px; border-left: 4px solid #dc3545; margin: 15px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ System Error</h1>
                    <p>Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
                
                <div class="content">
                    <h2>Error Details</h2>
                    <div class="highlight">
                        <strong>Type:</strong> {error_type}<br>
                        <strong>Message:</strong> {error_message}
                    </div>
                    
                    {context_html}
                    
                    <h3>Action Required</h3>
                    <p>Please investigate this error and take appropriate action to resolve the issue.</p>
                </div>
                
                <div class="footer">
                    <p>This notification was sent by LinkedIn Automation API</p>
                </div>
            </div>
        </body>
        </html>
        """

# Global notification service instance
_notification_service = None

def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service

# Legacy function for backward compatibility
def notify_lead_replied(lead, campaign, message_preview: Optional[str] = None) -> None:
    """Legacy function - now uses the new notification service."""
    try:
        from src.models import LinkedInAccount
        
        # Get the LinkedIn account for this campaign
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            logger.warning(f"No connected LinkedIn account found for campaign {campaign.id}")
            return
        
        notification_service = get_notification_service()
        notification_service.send_reply_notification(
            lead=lead,
            campaign=campaign,
            linkedin_account=linkedin_account,
            message_preview=message_preview
        )
    except Exception as e:
        logger.error(f"Error in notify_lead_replied: {str(e)}")


