#!/usr/bin/env python3
"""
Test script for notification system
"""
import os
import sys
from datetime import datetime

# Set environment variables for testing
os.environ['RESEND_API_KEY'] = 're_3DxGzHUD_9qNHenaxCE9bATUcL6oz3PUr'
os.environ['NOTIFY_EMAIL_TO'] = 'michael@costperdemo.com'
os.environ['NOTIFY_EMAIL_FROM'] = 'notifications@send.notifications.costperdemo.com'
os.environ['NOTIFICATIONS_ENABLED'] = 'true'

# Add src to path
sys.path.insert(0, 'src')

def test_notification_service():
    """Test the notification service"""
    print("🧪 Testing Notification Service...")
    
    try:
        from services.notifications import get_notification_service
        
        service = get_notification_service()
        print(f"✅ Service created successfully")
        print(f"   Enabled: {service.enabled}")
        print(f"   API Key: {service.resend_api_key[:10]}..." if service.resend_api_key else "None")
        print(f"   From Email: {service.from_email}")
        print(f"   To Emails: {service.to_emails}")
        
        if not service.enabled:
            print("❌ Service is disabled")
            return False
            
        # Test simple email sending
        print("\n📧 Testing simple email...")
        import resend
        resend.api_key = service.resend_api_key
        
        try:
            # Try with a simpler email first
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",  # Use Resend's default domain
                "to": service.to_emails[0],
                "subject": "🧪 Local Test - LinkedIn Automation API",
                "html": f"""
                <h2>Local Test Notification</h2>
                <p>This is a test from your local development environment.</p>
                <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>If you receive this email, the notification system is working locally!</p>
                """
            })
            
            print(f"✅ Email sent successfully with default domain!")
            print(f"   Email ID: {response.get('id')}")
            print(f"   Response: {response}")
            
            # Now try with your custom domain
            print("\n📧 Testing with custom domain...")
            response2 = resend.Emails.send({
                "from": service.from_email,
                "to": service.to_emails[0],
                "subject": "🧪 Custom Domain Test - LinkedIn Automation API",
                "html": f"""
                <h2>Custom Domain Test</h2>
                <p>This is a test using your custom domain.</p>
                <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                """
            })
            
            print(f"✅ Email sent successfully with custom domain!")
            print(f"   Email ID: {response2.get('id')}")
            return True
            
        except Exception as e:
            print(f"❌ Resend API Error: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
            if hasattr(e, 'status_code'):
                print(f"   Status code: {e.status_code}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response}")
            return False
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_notification_templates():
    """Test notification templates"""
    print("\n🎨 Testing notification templates...")
    
    try:
        from services.notifications import get_notification_service
        
        service = get_notification_service()
        
        # Create mock objects for testing
        class MockLead:
            def __init__(self):
                self.id = "test-lead-123"
                self.first_name = "John"
                self.last_name = "Doe"
                self.full_name = "John Doe"
                self.company_name = "Test Company"
                self.campaign = MockCampaign()
        
        class MockCampaign:
            def __init__(self):
                self.id = "test-campaign-456"
                self.name = "Test Campaign"
        
        class MockLinkedInAccount:
            def __init__(self):
                self.account_id = "test-account-789"
                self.name = "Test LinkedIn Account"
        
        # Test reply notification template
        print("   Testing reply notification template...")
        html = service._create_reply_notification_template(
            lead=MockLead(),
            campaign=MockCampaign(),
            linkedin_account=MockLinkedInAccount(),
            message_preview="Hi, I'm interested in your services!"
        )
        print(f"   ✅ Reply template created ({len(html)} characters)")
        
        # Test connection notification template
        print("   Testing connection notification template...")
        html = service._create_connection_notification_template(
            lead=MockLead(),
            campaign=MockCampaign(),
            linkedin_account=MockLinkedInAccount()
        )
        print(f"   ✅ Connection template created ({len(html)} characters)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing templates: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 LinkedIn Automation API - Notification System Test")
    print("=" * 60)
    
    # Test 1: Basic service functionality
    service_ok = test_notification_service()
    
    # Test 2: Template generation
    template_ok = test_notification_templates()
    
    print("\n" + "=" * 60)
    if service_ok and template_ok:
        print("🎉 All tests passed! Notification system is working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("\n📧 Check your email (michael@costperdemo.com) for the test message!")
