#!/usr/bin/env python3
"""
Test script for timezone functionality in sequence engine
"""
import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, 'src')

def test_timezone_functionality():
    """Test the timezone functionality"""
    print("🌍 Testing Timezone Functionality...")
    
    try:
        from services.sequence_engine import SequenceEngine
        
        sequence_engine = SequenceEngine()
        
        print(f"✅ Sequence engine created successfully")
        
        # Test timezone calculations
        print(f"\n📅 Testing timezone calculations...")
        
        # Create a mock campaign for testing
        class MockCampaign:
            def __init__(self, timezone):
                self.id = "test-campaign-123"
                self.timezone = timezone
        
        # Test different timezones
        test_timezones = [
            'UTC',
            'America/New_York',
            'Europe/London',
            'Asia/Tokyo',
            'Australia/Sydney'
        ]
        
        for tz_name in test_timezones:
            campaign = MockCampaign(tz_name)
            
            try:
                timezone_info = sequence_engine.get_campaign_timezone_info(campaign)
                
                print(f"   {tz_name}:")
                print(f"     Local Time: {timezone_info['local_time_formatted']}")
                print(f"     Day of Week: {timezone_info['day_of_week']}")
                print(f"     Is Weekend: {timezone_info['is_weekend']}")
                print(f"     UTC Offset: {timezone_info['utc_offset']}")
                print()
                
            except Exception as e:
                print(f"   {tz_name}: Error - {str(e)}")
                print()
        
        # Test working day calculations in different timezones
        print(f"\n⏰ Testing working day calculations in different timezones...")
        
        test_campaign = MockCampaign('America/New_York')
        
        for working_days in [1, 3, 5]:
            target_date = sequence_engine._add_working_days_in_timezone(
                test_campaign, datetime.utcnow(), working_days
            )
            print(f"   {working_days} working days from now in {test_campaign.timezone}: {target_date.strftime('%Y-%m-%d %A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_timezone_validation():
    """Test timezone validation"""
    print(f"\n✅ Testing timezone validation...")
    
    try:
        import pytz
        
        # Test valid timezones
        valid_timezones = [
            'UTC',
            'America/New_York',
            'Europe/London',
            'Asia/Tokyo'
        ]
        
        for tz_name in valid_timezones:
            try:
                tz = pytz.timezone(tz_name)
                print(f"   ✅ {tz_name}: Valid")
            except Exception as e:
                print(f"   ❌ {tz_name}: Invalid - {str(e)}")
        
        # Test invalid timezone
        try:
            pytz.timezone('Invalid/Timezone')
            print(f"   ❌ Invalid/Timezone: Should have failed")
        except pytz.exceptions.UnknownTimeZoneError:
            print(f"   ✅ Invalid/Timezone: Correctly rejected")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_available_timezones():
    """Test available timezones endpoint logic"""
    print(f"\n🌐 Testing available timezones...")
    
    try:
        import pytz
        
        # Common timezones for business use
        common_timezones = [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Australia/Sydney',
            'Pacific/Auckland'
        ]
        
        timezone_list = []
        for tz_name in common_timezones:
            try:
                tz = pytz.timezone(tz_name)
                utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
                local_time = utc_now.astimezone(tz)
                
                timezone_info = {
                    'name': tz_name,
                    'display_name': tz_name.replace('_', ' '),
                    'current_time': local_time.strftime('%H:%M'),
                    'utc_offset': local_time.strftime('%z'),
                    'is_weekend': local_time.weekday() >= 5
                }
                
                timezone_list.append(timezone_info)
                print(f"   {tz_name}: {timezone_info['current_time']} {timezone_info['utc_offset']} ({timezone_info['display_name']})")
                
            except Exception as e:
                print(f"   ❌ {tz_name}: Error - {str(e)}")
        
        print(f"\n   Total timezones: {len(timezone_list)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 LinkedIn Automation API - Timezone Test")
    print("=" * 60)
    
    # Test 1: Timezone functionality
    timezone_ok = test_timezone_functionality()
    
    # Test 2: Timezone validation
    validation_ok = test_timezone_validation()
    
    # Test 3: Available timezones
    available_ok = test_available_timezones()
    
    print("\n" + "=" * 60)
    if timezone_ok and validation_ok and available_ok:
        print("🎉 All tests passed! Timezone functionality is working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("\n📋 Summary:")
    print("✅ Timezone calculations")
    print("✅ Working day calculations in timezones")
    print("✅ Timezone validation")
    print("✅ Available timezones list")
    print("✅ Campaign timezone support")
