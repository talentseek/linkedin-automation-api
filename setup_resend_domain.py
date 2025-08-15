#!/usr/bin/env python3
"""
Resend Domain Setup and Management Script
"""
import os
import sys
import resend

# Set up API key
resend.api_key = "re_3DxGzHUD_9qNHenaxCE9bATUcL6oz3PUr"

def list_domains():
    """List all domains"""
    print("📋 Listing all domains...")
    try:
        response = resend.Domains.list()
        print(f"✅ Found {len(response)} domains:")
        for domain in response:
            if isinstance(domain, dict):
                print(f"   - {domain.get('name')} (ID: {domain.get('id')})")
                print(f"     Status: {domain.get('status')}")
                print(f"     Created: {domain.get('created_at')}")
                print(f"     Region: {domain.get('region')}")
            else:
                print(f"   - {domain}")
            print()
        return response
    except Exception as e:
        print(f"❌ Error listing domains: {str(e)}")
        return []

def create_domain(domain_name):
    """Create a new domain"""
    print(f"🏗️ Creating domain: {domain_name}")
    try:
        params = {
            "name": domain_name,
        }
        response = resend.Domains.create(params)
        print(f"✅ Domain created successfully!")
        print(f"   ID: {response.get('id')}")
        print(f"   Name: {response.get('name')}")
        print(f"   Status: {response.get('status')}")
        print(f"   Created: {response.get('created_at')}")
        return response
    except Exception as e:
        print(f"❌ Error creating domain: {str(e)}")
        return None

def get_domain(domain_id):
    """Get domain details"""
    print(f"🔍 Getting domain details for ID: {domain_id}")
    try:
        response = resend.Domains.get(domain_id=domain_id)
        print(f"✅ Domain details:")
        print(f"   ID: {response.get('id')}")
        print(f"   Name: {response.get('name')}")
        print(f"   Status: {response.get('status')}")
        print(f"   Created: {response.get('created_at')}")
        print(f"   Region: {response.get('region')}")
        return response
    except Exception as e:
        print(f"❌ Error getting domain: {str(e)}")
        return None

def verify_domain(domain_id):
    """Verify a domain"""
    print(f"✅ Verifying domain ID: {domain_id}")
    try:
        response = resend.Domains.verify(domain_id=domain_id)
        print(f"✅ Domain verification initiated!")
        print(f"   ID: {response.get('id')}")
        print(f"   Name: {response.get('name')}")
        print(f"   Status: {response.get('status')}")
        return response
    except Exception as e:
        print(f"❌ Error verifying domain: {str(e)}")
        return None

def update_domain(domain_id, open_tracking=True, click_tracking=True):
    """Update domain settings"""
    print(f"⚙️ Updating domain settings for ID: {domain_id}")
    try:
        params = {
            "id": domain_id,
            "open_tracking": open_tracking,
            "click_tracking": click_tracking,
        }
        response = resend.Domains.update(params)
        print(f"✅ Domain updated successfully!")
        print(f"   Open tracking: {response.get('open_tracking')}")
        print(f"   Click tracking: {response.get('click_tracking')}")
        return response
    except Exception as e:
        print(f"❌ Error updating domain: {str(e)}")
        return None

def remove_domain(domain_id):
    """Remove a domain"""
    print(f"🗑️ Removing domain ID: {domain_id}")
    try:
        response = resend.Domains.remove(domain_id=domain_id)
        print(f"✅ Domain removed successfully!")
        return True
    except Exception as e:
        print(f"❌ Error removing domain: {str(e)}")
        return False

def test_domain_email(domain_name):
    """Test sending email with the domain"""
    print(f"📧 Testing email with domain: {domain_name}")
    try:
        response = resend.Emails.send({
            "from": f"test@{domain_name}",
            "to": "michael@costperdemo.com",
            "subject": "🧪 Domain Test - LinkedIn Automation API",
            "html": f"""
            <h2>Domain Test</h2>
            <p>This is a test email using the domain: <strong>{domain_name}</strong></p>
            <p>If you receive this email, the domain is working correctly!</p>
            """
        })
        print(f"✅ Test email sent successfully!")
        print(f"   Email ID: {response.get('id')}")
        return True
    except Exception as e:
        print(f"❌ Error sending test email: {str(e)}")
        return False

def main():
    print("🚀 Resend Domain Management")
    print("=" * 50)
    
    # List existing domains
    domains = list_domains()
    
    # Check if our domain already exists
    target_domain = "send.notifications.costperdemo.com"
    existing_domain = None
    
    for domain in domains:
        if isinstance(domain, dict) and domain.get('name') == target_domain:
            existing_domain = domain
            break
        elif isinstance(domain, str) and domain == target_domain:
            existing_domain = {'name': domain}
            break
    
    if existing_domain:
        print(f"✅ Domain {target_domain} already exists!")
        if isinstance(existing_domain, dict):
            print(f"   ID: {existing_domain.get('id', 'Unknown')}")
            print(f"   Status: {existing_domain.get('status', 'Unknown')}")
            
            # Get detailed info if we have an ID
            if existing_domain.get('id'):
                get_domain(existing_domain.get('id'))
                
                # If not verified, try to verify
                if existing_domain.get('status') != "valid":
                    print(f"\n🔄 Domain is not verified. Attempting verification...")
                    verify_domain(existing_domain.get('id'))
                else:
                    print(f"\n✅ Domain is verified! Testing email...")
                    test_domain_email(target_domain)
            else:
                print(f"\n📋 Domain exists but we need to get its details.")
                print("Please check the Resend dashboard for domain verification status.")
        else:
            print(f"\n📋 Domain exists but we need to get its details.")
            print("Please check the Resend dashboard for domain verification status.")
    else:
        print(f"\n🏗️ Domain {target_domain} does not exist. Creating...")
        new_domain = create_domain(target_domain)
        
        if new_domain:
            print(f"\n📋 DNS Records needed for {target_domain}:")
            print("Please add these DNS records to your domain:")
            print()
            print("MX Record:")
            print(f"  Name: {target_domain}")
            print(f"  Value: feedback-smtp.eu-west-1.amazonses.com")
            print(f"  Priority: 10")
            print()
            print("TXT Record (SPF):")
            print(f"  Name: {target_domain}")
            print(f"  Value: v=spf1 include:amazonses.com ~all")
            print()
            print("TXT Record (DKIM):")
            print(f"  Name: resend._domainkey.{target_domain}")
            print(f"  Value: [Will be provided by Resend]")
            print()
            print("After adding DNS records, run this script again to verify the domain.")

if __name__ == "__main__":
    main()
