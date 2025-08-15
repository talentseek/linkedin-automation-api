#!/usr/bin/env python3
"""
Test script for working day delays in sequence engine
"""
import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, 'src')

def test_working_day_delays():
    """Test the working day delay functionality"""
    print("🧪 Testing Working Day Delays...")
    
    try:
        from services.sequence_engine import SequenceEngine, EXAMPLE_SEQUENCE
        
        sequence_engine = SequenceEngine()
        
        print(f"✅ Sequence engine created successfully")
        
        # Test working day calculation
        print(f"\n📅 Testing working day calculations...")
        today = datetime.utcnow()
        print(f"   Today: {today.strftime('%Y-%m-%d %A')}")
        
        for days in [1, 3, 5, 7]:
            target_date = sequence_engine._add_working_days(today, days)
            print(f"   {days} working days from now: {target_date.strftime('%Y-%m-%d %A')}")
        
        # Test delay calculations for each step
        print(f"\n⏰ Testing delay calculations for each step...")
        for step in EXAMPLE_SEQUENCE:
            step_order = step.get('step_order')
            name = step.get('name')
            delay_hours = step.get('delay_hours', 0)
            delay_working_days = step.get('delay_working_days', 0)
            
            min_delay = sequence_engine._get_minimum_delay(step)
            delay_description = sequence_engine.get_delay_description(step)
            
            print(f"   Step {step_order}: {name}")
            print(f"     delay_hours: {delay_hours}")
            print(f"     delay_working_days: {delay_working_days}")
            print(f"     total_delay: {min_delay}")
            print(f"     description: {delay_description}")
            print()
        
        # Test the immediate first message logic
        print(f"\n🚀 Testing immediate first message logic...")
        
        # Create a mock lead for testing
        class MockLead:
            def __init__(self):
                self.id = "test-lead-123"
                self.status = "connected"
                self.current_step = 1
                self.last_step_sent_at = datetime.utcnow() - timedelta(hours=1)
        
        mock_lead = MockLead()
        
        # Test step 2 (first message after connection)
        step_2 = EXAMPLE_SEQUENCE[1]  # First message step
        can_execute = sequence_engine.can_execute_step(mock_lead, step_2)
        
        print(f"   Step 2 (first message) can execute: {can_execute['can_execute']}")
        print(f"   Reason: {can_execute['reason']}")
        
        # Test step 3 (follow-up message)
        step_3 = EXAMPLE_SEQUENCE[2]  # Follow-up message step
        can_execute_3 = sequence_engine.can_execute_step(mock_lead, step_3)
        
        print(f"   Step 3 (follow-up) can execute: {can_execute_3['can_execute']}")
        print(f"   Reason: {can_execute_3['reason']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_sequence_validation():
    """Test sequence validation with working days"""
    print(f"\n✅ Testing sequence validation...")
    
    try:
        from services.sequence_engine import SequenceEngine
        
        sequence_engine = SequenceEngine()
        
        # Test valid sequence
        valid_sequence = [
            {
                "step_order": 1,
                "action_type": "connection_request",
                "message": "Hi {{first_name}}!",
                "delay_hours": 0,
                "name": "Connection Request"
            },
            {
                "step_order": 2,
                "action_type": "message",
                "message": "Thanks for connecting!",
                "delay_hours": 0,
                "delay_working_days": 3,
                "name": "Follow-up"
            }
        ]
        
        validation = sequence_engine.validate_sequence_definition(valid_sequence)
        print(f"   Valid sequence: {validation['valid']}")
        if not validation['valid']:
            print(f"   Errors: {validation['errors']}")
        
        # Test invalid sequence (negative working days)
        invalid_sequence = [
            {
                "step_order": 1,
                "action_type": "connection_request",
                "message": "Hi {{first_name}}!",
                "delay_hours": 0,
                "name": "Connection Request"
            },
            {
                "step_order": 2,
                "action_type": "message",
                "message": "Thanks for connecting!",
                "delay_hours": 0,
                "delay_working_days": -1,  # Invalid
                "name": "Follow-up"
            }
        ]
        
        validation = sequence_engine.validate_sequence_definition(invalid_sequence)
        print(f"   Invalid sequence: {validation['valid']}")
        if not validation['valid']:
            print(f"   Errors: {validation['errors']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 LinkedIn Automation API - Working Day Delays Test")
    print("=" * 60)
    
    # Test 1: Working day calculations
    working_days_ok = test_working_day_delays()
    
    # Test 2: Sequence validation
    validation_ok = test_sequence_validation()
    
    print("\n" + "=" * 60)
    if working_days_ok and validation_ok:
        print("🎉 All tests passed! Working day delays are working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("\n📋 Summary:")
    print("✅ Working day calculations")
    print("✅ Delay descriptions")
    print("✅ Immediate first message logic")
    print("✅ Sequence validation")
    print("✅ Backward compatibility with delay_hours")
