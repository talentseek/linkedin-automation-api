"""
Core sequence engine functionality.

This module contains the main sequence engine class and core functionality:
- SequenceEngine class
- Main execution logic
- Step processing
- Sequence management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import calendar
import pytz

from src.extensions import db
from src.models import Lead, Campaign, Event
from src.services.unipile_client import UnipileClient

logger = logging.getLogger(__name__)

# Example sequence definition with both delay formats
EXAMPLE_SEQUENCE = [
    {
        "step_order": 1,
        "action_type": "connection_request",
        "message": "Hi {{first_name}}, I work with distributors to automate order processing. Would love to connect and share insights!",
        "delay_hours": 0,
        "name": "Connection Request"
    },
    {
        "step_order": 2,
        "action_type": "message",
        "message": "Hi {{first_name}}, thanks for connecting! I'd love to learn more about {{company_name}}. Any chance you'd be open to a quick chat?",
        "delay_hours": 0,  # No delay - immediate after connection acceptance
        "name": "First Message (Immediate)"
    },
    {
        "step_order": 3,
        "action_type": "message",
        "message": "Hi {{first_name}}, just following up on my previous message. Would you be interested in a 15-minute call to explore potential collaboration?",
        "delay_hours": 0,
        "delay_working_days": 3,  # 3 working days after first message
        "name": "Follow-up Message"
    },
    {
        "step_order": 4,
        "action_type": "message",
        "message": "Hi {{first_name}}, final follow-up here. If you're interested in exploring automation solutions, I'd be happy to share some case studies. No pressure!",
        "delay_hours": 0,
        "delay_working_days": 5,  # 5 working days after previous message
        "name": "Final Follow-up"
    }
]

class SequenceEngine:
    """Engine for managing and executing LinkedIn outreach sequences."""
    
    def __init__(self):
        """Initialize the sequence engine."""
        self.unipile = None  # Initialize lazily
    
    def _get_unipile_client(self):
        """Get Unipile client instance (lazy initialization)."""
        if self.unipile is None:
            self.unipile = UnipileClient()
        return self.unipile
    
    def execute_step(self, lead: Lead, step: Dict[str, Any], linkedin_account) -> Dict[str, Any]:
        """Execute a single step in the sequence."""
        try:
            # CRITICAL FIX: Always refresh lead from database to ensure correct data
            try:
                db.session.refresh(lead)
                logger.info(f"=== LEAD DATA VERIFICATION ===")
                logger.info(f"Lead ID: {lead.id}")
                logger.info(f"Lead Name: {lead.first_name} {lead.last_name}")
                logger.info(f"Lead Company: {lead.company_name}")
                logger.info(f"Lead Status: {lead.status}")
                logger.info(f"Lead Current Step: {lead.current_step}")
                logger.info(f"=== END LEAD DATA VERIFICATION ===")
            except Exception as refresh_error:
                logger.error(f"Failed to refresh lead {lead.id}: {str(refresh_error)}")
                return {'success': False, 'error': f'Failed to refresh lead data: {str(refresh_error)}'}
            
            # Validate lead object
            if not lead or not hasattr(lead, 'id'):
                logger.error("Invalid lead object provided")
                return {'success': False, 'error': 'Invalid lead object'}
            
            # Get step details
            action_type = step.get('action_type')
            message = step.get('message', '')
            
            logger.info(f"=== EXECUTE STEP DEBUG ===")
            logger.info(f"Action type: {action_type}")
            logger.info(f"Original message: '{message}'")
            logger.info(f"Step data: {step}")
            logger.info(f"=== END EXECUTE STEP DEBUG ===")
            
            # Format message with lead data
            formatted_message = self._format_message(message, lead)
            
            # Execute based on action type
            if action_type == 'connection_request':
                result = self._send_connection_request(lead, linkedin_account, formatted_message)
            elif action_type == 'message':
                result = self._send_message(lead, linkedin_account, formatted_message)
            else:
                logger.error(f"Unknown action type: {action_type}")
                return {'success': False, 'error': f'Unknown action type: {action_type}'}
            
            # Create event for tracking
            event = Event(
                event_type=f'step_{action_type}_executed',
                lead_id=lead.id,
                meta_json={
                    'step_data': step,
                    'formatted_message': formatted_message,
                    'result': result
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Step execution completed for lead {lead.id}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing step for lead {lead.id}: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_sequence_info(self, campaign: Campaign) -> Dict[str, Any]:
        """Get information about a campaign's sequence."""
        try:
            sequence = campaign.sequence_json
            if not sequence:
                return {'steps': [], 'total_steps': 0}
            
            return {
                'steps': sequence,
                'total_steps': len(sequence),
                'timezone': campaign.timezone
            }
            
        except Exception as e:
            logger.error(f"Error getting sequence info: {str(e)}")
            return {'steps': [], 'total_steps': 0}
    
    def validate_sequence(self, sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a sequence definition."""
        try:
            errors = []
            warnings = []
            
            if not sequence:
                errors.append("Sequence cannot be empty")
                return {'valid': False, 'errors': errors, 'warnings': warnings}
            
            for i, step in enumerate(sequence):
                # Check required fields
                if 'action_type' not in step:
                    errors.append(f"Step {i+1}: Missing action_type")
                
                if 'message' not in step:
                    errors.append(f"Step {i+1}: Missing message")
                
                # Check action type
                action_type = step.get('action_type')
                if action_type not in ['connection_request', 'message']:
                    errors.append(f"Step {i+1}: Invalid action_type '{action_type}'")
                
                # Check delay configuration
                delay_hours = step.get('delay_hours', 0)
                delay_working_days = step.get('delay_working_days', 0)
                
                if delay_hours < 0:
                    errors.append(f"Step {i+1}: delay_hours cannot be negative")
                
                if delay_working_days < 0:
                    errors.append(f"Step {i+1}: delay_working_days cannot be negative")
                
                # Check for personalization placeholders
                message = step.get('message', '')
                if '{{' in message and '}}' in message:
                    # This is good - has personalization
                    pass
                else:
                    warnings.append(f"Step {i+1}: No personalization placeholders found")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating sequence: {str(e)}")
            return {'valid': False, 'errors': [str(e)], 'warnings': []}
    
    # Import functionality from other modules
    from .timezone import _get_campaign_timezone, _get_campaign_local_time, _is_weekend_in_timezone, _add_working_days_in_timezone
    from .delay_calculator import _calculate_delay, _get_minimum_delay, _add_working_days
    from .message_formatter import _format_message
    from .action_executor import _send_connection_request, _send_message
