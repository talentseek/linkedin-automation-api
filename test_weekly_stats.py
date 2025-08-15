#!/usr/bin/env python3
"""
Test script for weekly statistics system
"""
import os
import sys
from datetime import datetime, timedelta

# Set environment variables for testing
os.environ['RESEND_API_KEY'] = 're_3DxGzHUD_9qNHenaxCE9bATUcL6oz3PUr'
os.environ['NOTIFY_EMAIL_FROM'] = 'notifications@notifications.costperdemo.com'
os.environ['WEEKLY_STATS_ENABLED'] = 'true'

# Add src to path
sys.path.insert(0, 'src')

def test_weekly_statistics_service():
    """Test the weekly statistics service"""
    print("🧪 Testing Weekly Statistics Service...")
    
    try:
        from services.weekly_statistics import get_weekly_statistics_service
        from main import app
        
        service = get_weekly_statistics_service()
        print(f"✅ Service created successfully")
        print(f"   Enabled: {service.enabled}")
        print(f"   API Key: {service.resend_api_key[:10]}..." if service.resend_api_key else "None")
        print(f"   From Email: {service.from_email}")
        
        if not service.enabled:
            print("❌ Service is disabled")
            return False
        
        # Test statistics generation with app context
        print("\n📊 Testing statistics generation...")
        
        with app.app_context():
            # Get a sample client ID
            from models import Client
            clients = Client.query.all()
            
            if not clients:
                print("❌ No clients found in database")
                return False
            
            client = clients[0]
            print(f"   Using client: {client.name} (ID: {client.id})")
            
            # Calculate date range (last 7 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            # Generate statistics
            stats = service.generate_client_statistics(client.id, start_date, end_date)
            
            if stats:
                print(f"✅ Statistics generated successfully!")
                print(f"   Client: {stats['client'].name}")
                print(f"   Period: {stats['period']['start'].strftime('%Y-%m-%d')} to {stats['period']['end'].strftime('%Y-%m-%d')}")
                print(f"   Total Leads: {stats['summary']['total_leads']}")
                print(f"   Connections: {stats['summary']['connections']}")
                print(f"   Replies: {stats['summary']['replies']}")
                print(f"   Conversion Rate: {stats['summary']['conversion_rate']:.1f}%")
                print(f"   Campaigns: {len(stats['campaigns'])}")
                
                # Test email sending
                print(f"\n📧 Testing weekly report email...")
                success = service.send_weekly_report(client.id, 'michael@costperdemo.com')
                
                if success:
                    print(f"✅ Weekly report sent successfully!")
                    return True
                else:
                    print(f"❌ Failed to send weekly report")
                    return False
            else:
                print(f"❌ Failed to generate statistics")
                return False
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_weekly_report_template():
    """Test the weekly report template generation"""
    print("\n🎨 Testing weekly report template...")
    
    try:
        from services.weekly_statistics import get_weekly_statistics_service
        
        service = get_weekly_statistics_service()
        
        # Create mock statistics data
        class MockClient:
            def __init__(self):
                self.id = "test-client-123"
                self.name = "Test Client"
                self.email = "test@example.com"
        
        class MockCampaign:
            def __init__(self):
                self.id = "test-campaign-456"
                self.name = "Test Campaign"
                self.status = "active"
        
        mock_stats = {
            'client': MockClient(),
            'period': {
                'start': datetime.utcnow() - timedelta(days=7),
                'end': datetime.utcnow()
            },
            'summary': {
                'total_leads': 25,
                'new_leads': 15,
                'connections': 8,
                'replies': 3,
                'messages_sent': 12,
                'conversion_rate': 32.0
            },
            'campaigns': [
                {
                    'campaign': MockCampaign(),
                    'total_leads': 25,
                    'new_leads': 15,
                    'connections': 8,
                    'replies': 3,
                    'messages_sent': 12,
                    'conversion_rate': 32.0
                }
            ],
            'recent_activity': {
                'new_leads': 5,
                'new_events': 12,
                'recent_replies': 2,
                'recent_connections': 3
            }
        }
        
        # Generate template
        html = service._create_weekly_report_template(mock_stats)
        print(f"   ✅ Template generated successfully ({len(html)} characters)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing template: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 LinkedIn Automation API - Weekly Statistics Test")
    print("=" * 60)
    
    # Test 1: Service functionality
    service_ok = test_weekly_statistics_service()
    
    # Test 2: Template generation
    template_ok = test_weekly_report_template()
    
    print("\n" + "=" * 60)
    if service_ok and template_ok:
        print("🎉 All tests passed! Weekly statistics system is working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("\n📧 Check your email (michael@costperdemo.com) for the weekly report!")
