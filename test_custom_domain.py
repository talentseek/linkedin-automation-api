#!/usr/bin/env python3
"""
Test custom domain directly
"""
import resend

# Set up API key
resend.api_key = "re_3DxGzHUD_9qNHenaxCE9bATUcL6oz3PUr"

def test_custom_domain():
    """Test sending email with custom domain"""
    print("🧪 Testing Custom Domain Email")
    print("=" * 40)
    
    try:
        # Test with custom domain
        response = resend.Emails.send({
            "from": "notifications@notifications.costperdemo.com",
            "to": "michael@costperdemo.com",
            "subject": "🧪 Custom Domain Test - LinkedIn Automation API",
            "html": """
            <h2>Custom Domain Test</h2>
            <p>This is a test email using your custom domain: <strong>notifications.costperdemo.com</strong></p>
            <p>If you receive this email, your custom domain is working correctly!</p>
            <p><strong>Time:</strong> """ + str(__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')) + """</p>
            """
        })
        
        print(f"✅ Custom domain email sent successfully!")
        print(f"   Email ID: {response.get('id')}")
        print(f"   Response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Error with custom domain: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        
        # Try with default domain as fallback
        print(f"\n🔄 Trying with default domain as fallback...")
        try:
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": "michael@costperdemo.com",
                "subject": "🧪 Fallback Test - LinkedIn Automation API",
                "html": """
                <h2>Fallback Test</h2>
                <p>This is a fallback test using the default Resend domain.</p>
                <p>Your custom domain needs DNS verification.</p>
                """
            })
            print(f"✅ Fallback email sent successfully!")
            print(f"   Email ID: {response.get('id')}")
            return False
        except Exception as e2:
            print(f"❌ Fallback also failed: {str(e2)}")
            return False

if __name__ == "__main__":
    test_custom_domain()
