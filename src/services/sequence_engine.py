import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.extensions import db
from src.models import Lead, Campaign, Event
from src.services.unipile_client import UnipileClient

logger = logging.getLogger(__name__)

# Example sequence definition with short messages
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
        "delay_hours": 24,
        "name": "Follow-up Message"
    },
    {
        "step_order": 3,
        "action_type": "message",
        "message": "Hi {{first_name}}, just following up on my previous message. Would you be interested in a 15-minute call to explore potential collaboration?",
        "delay_hours": 72,
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
    
    def validate_and_truncate_message(self, message: str, max_length: int = 300) -> str:
        """Validate and truncate message to fit LinkedIn's character limit."""
        if len(message) <= max_length:
            return message
        
        # Truncate and add ellipsis
        truncated = message[:max_length-3] + "..."
        logger.warning(f"Message truncated from {len(message)} to {len(truncated)} characters")
        return truncated
    
    def get_next_step_for_lead(self, lead: Lead) -> Optional[Dict[str, Any]]:
        """Get the next step for a lead based on their current status."""
        try:
            campaign = lead.campaign
            if not campaign.sequence:
                logger.warning(f"No sequence defined for campaign {campaign.id}")
                # Auto-assign default sequence if none exists
                try:
                    campaign.sequence_json = EXAMPLE_SEQUENCE
                    db.session.commit()
                    logger.info(f"Auto-assigned default sequence to campaign {campaign.id}")
                except Exception as e:
                    logger.error(f"Failed to auto-assign sequence: {str(e)}")
                    return None
            
            sequence = campaign.sequence
            current_step = lead.current_step or 0
            
            # Special handling for 1st level connections (already connected)
            is_first_level_connection = lead.meta_json and lead.meta_json.get('source') == 'first_level_connections'
            
            # Find the next step in the sequence
            for step in sequence:
                if step['step_order'] > current_step:
                    # For 1st level connections, skip connection request steps
                    if is_first_level_connection and step.get('action_type') == 'connection_request':
                        continue
                    return step
            
            # No more steps in sequence
            return None
            
        except Exception as e:
            logger.error(f"Error getting next step for lead {lead.id}: {str(e)}")
            return None
    
    def can_execute_step(self, lead: Lead, step: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a step can be executed for a lead."""
        try:
            # Immediate first message after connection acceptance
            # If the next action is a message and the lead is connected, allow immediately
            # regardless of the previous last_step_sent_at timing.
            action_type = step.get('action_type')
            if action_type == 'message' and lead.status == 'connected' and (lead.current_step or 0) < 2:
                # Only the first post-accept message skips delay; subsequent messages keep delay logic
                return {'can_execute': True, 'reason': 'Immediate post-accept first message allowed'}

            # Check if enough time has passed since the last step
            if lead.last_step_sent_at:
                delay_hours = step.get('delay_hours', 24)
                min_delay = timedelta(hours=delay_hours)
                time_since_last = datetime.utcnow() - lead.last_step_sent_at
                
                if time_since_last < min_delay:
                    remaining_time = min_delay - time_since_last
                    return {
                        'can_execute': False,
                        'reason': f'Waiting for delay period. {remaining_time} remaining.'
                    }
            
            # Check if lead is in the correct status for this step
            action_type = step.get('action_type')
            
            # Special handling for 1st level connections (already connected)
            is_first_level_connection = lead.meta_json and lead.meta_json.get('source') == 'first_level_connections'
            
            if action_type == 'connection_request':
                if is_first_level_connection:
                    # Skip connection requests for 1st level connections
                    return {
                        'can_execute': False,
                        'reason': 'Skipping connection request for 1st level connection'
                    }
                elif lead.status != 'pending_invite':
                    return {
                        'can_execute': False,
                        'reason': f'Lead status is {lead.status}, expected pending_invite for connection request'
                    }
            elif action_type == 'message':
                if lead.status != 'connected':
                    return {
                        'can_execute': False,
                        'reason': f'Lead status is {lead.status}, expected connected for message'
                    }
            
            return {'can_execute': True, 'reason': 'Step can be executed'}
            
        except Exception as e:
            logger.error(f"Error checking if step can be executed for lead {lead.id}: {str(e)}")
            return {'can_execute': False, 'reason': f'Error: {str(e)}'}
    
    def execute_step(self, lead: Lead, step: Dict[str, Any], linkedin_account) -> Dict[str, Any]:
        """Execute a step for a lead."""
        try:
            action_type = step.get('action_type')
            message = step.get('message', '')
            
            # Format message with lead data
            formatted_message = self._format_message(message, lead)
            
            if action_type == 'connection_request':
                return self._send_connection_request(lead, linkedin_account, formatted_message)
            elif action_type == 'message':
                return self._send_message(lead, linkedin_account, formatted_message)
            else:
                return {
                    'success': False,
                    'error': f'Unknown action type: {action_type}'
                }
                
        except Exception as e:
            logger.error(f"Error executing step for lead {lead.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_message(self, message: str, lead: Lead) -> str:
        """Format a message with lead data."""
        try:
            logger.info(f"Formatting message for lead {lead.id}: {lead.first_name} {lead.last_name} at {lead.company_name}")
            logger.info(f"Original message: {message}")
            
            # Replace placeholders with actual data, using safe company fallback
            company_safe = None
            try:
                if lead.company_name and isinstance(lead.company_name, str) and lead.company_name.strip():
                    company_safe = lead.company_name.strip()
                else:
                    # Try to infer from a headline-like value mistakenly stored in company_name
                    from src.routes.lead import _extract_company_name_from_profile
                    company_safe = _extract_company_name_from_profile({'headline': lead.company_name}) or 'your company'
            except Exception:
                company_safe = 'your company'

            formatted = message.replace('{{first_name}}', lead.first_name or 'there')
            formatted = formatted.replace('{{last_name}}', lead.last_name or '')
            formatted = formatted.replace('{{company}}', company_safe)
            formatted = formatted.replace('{{company_name}}', company_safe)  # Also handle company_name variant
            # Note: title field doesn't exist in Lead model, so we'll skip it for now
            
            logger.info(f"Formatted message: {formatted}")
            return formatted
        except Exception as e:
            logger.error(f"Error formatting message: {str(e)}")
            return message
    
    def _send_connection_request(self, lead: Lead, linkedin_account, message: str) -> Dict[str, Any]:
        """Send a connection request to a lead."""
        try:
            # Use Unipile API to send connection request
            unipile = self._get_unipile_client()
            
            # Step 1: Get the profile to ensure we have the correct provider_id
            logger.info(f"Getting profile for lead {lead.id} via Unipile")
            profile_result = unipile.get_user_profile(
                identifier=lead.public_identifier,  # Use public_identifier first
                account_id=linkedin_account.account_id
            )
            
            logger.info(f"Unipile profile result: {profile_result}")
            
            # Extract the provider_id from the profile result
            provider_id = profile_result.get('provider_id')
            if not provider_id:
                return {
                    'success': False,
                    'error': 'Could not get provider_id from profile'
                }
            
            # Step 2: Send the actual connection request via Unipile
            logger.info(f"Sending connection request to lead {lead.id} via Unipile")
            
            # Validate and truncate message if needed
            validated_message = self.validate_and_truncate_message(message)
            
            result = unipile.send_connection_request(
                account_id=linkedin_account.account_id,
                profile_id=provider_id,
                message=validated_message
            )
            
            logger.info(f"Unipile connection request result: {result}")
            
            # Update lead status
            lead.status = 'invite_sent'
            lead.last_step_sent_at = datetime.utcnow()
            lead.current_step = (lead.current_step or 0) + 1
            
            # Create event record
            event = Event(
                lead_id=lead.id,
                event_type='connection_request_sent',
                meta_json={
                    'message': message,
                    'linkedin_account_id': linkedin_account.id,
                    'profile_result': profile_result,
                    'unipile_result': result
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Connection request sent to lead {lead.id}")
            
            return {
                'success': True,
                'message': 'Connection request sent successfully',
                'profile_result': profile_result,
                'unipile_result': result
            }
            
        except Exception as e:
            logger.error(f"Error sending connection request to lead {lead.id}: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_message(self, lead: Lead, linkedin_account, message: str) -> Dict[str, Any]:
        """Send a message to a connected lead."""
        try:
            # Use Unipile API to send message
            unipile = self._get_unipile_client()
            
            # Get conversation ID if not available
            conversation_id = lead.conversation_id
            if not conversation_id:
                logger.info(f"No conversation ID for lead {lead.id}, trying to locate chat or start one")
                try:
                    # Try to locate existing chat first
                    conversation_id = self._get_unipile_client().find_conversation_with_provider(
                        linkedin_account.account_id,
                        lead.provider_id,
                    )
                    if conversation_id:
                        lead.conversation_id = conversation_id
                        db.session.commit()
                        logger.info(f"Found and saved conversation ID {conversation_id} for lead {lead.id}")
                    else:
                        # Start 1:1 chat and send initial message per docs (no existing chat needed)
                        logger.info("No existing chat found; starting new chat via /api/v1/chats")
                        # Try to resolve a LinkedIn attendee ID suitable for chats API
                        attendee_id = lead.provider_id
                        try:
                            profile = self._get_unipile_client().get_user_profile(
                                identifier=attendee_id,
                                account_id=linkedin_account.account_id,
                            )
                            attendee_id = (
                                profile.get('member_id')
                                or profile.get('provider_id')
                                or attendee_id
                            )
                        except Exception:
                            pass

                        start_res = self._get_unipile_client().start_chat_with_attendee(
                            account_id=linkedin_account.account_id,
                            attendee_provider_id=attendee_id,
                            text=message,
                        )
                        # Try to extract chat id from response to persist for future steps
                        new_chat_id = (
                            (start_res.get('chat') or {}).get('id')
                            if isinstance(start_res, dict) and isinstance(start_res.get('chat'), dict)
                            else start_res.get('id')
                            if isinstance(start_res, dict) and start_res.get('id')
                            else start_res.get('chat_id')
                            if isinstance(start_res, dict)
                            else None
                        )
                        if new_chat_id:
                            lead.conversation_id = new_chat_id
                            db.session.commit()
                            logger.info(f"Started new chat {new_chat_id} for lead {lead.id}")
                        # Record event and return success immediately (message already sent in start chat)
                        event = Event(
                            lead_id=lead.id,
                            event_type='message_sent',
                            meta_json={
                                'message': message,
                                'linkedin_account_id': linkedin_account.id,
                                'unipile_result': start_res,
                                'method': 'start_chat_with_attendee'
                            }
                        )
                        db.session.add(event)
                        # Update sequencing timestamps/step progression
                        lead.last_step_sent_at = datetime.utcnow()
                        lead.current_step = (lead.current_step or 0) + 1
                        db.session.commit()
                        return {
                            'success': True,
                            'message': 'Message sent successfully (new chat started)',
                            'unipile_result': start_res
                        }
                except Exception as e:
                    logger.error(f"Error establishing chat for lead {lead.id}: {str(e)}")
                    return {
                        'success': False,
                        'error': f'Error establishing chat: {str(e)}'
                    }
            
            # Send the actual message via Unipile
            logger.info(f"Sending message to lead {lead.id} via Unipile")
            
            # Validate and truncate message if needed (LinkedIn messages have higher limit)
            validated_message = self.validate_and_truncate_message(message, max_length=1000)
            
            try:
                result = unipile.send_message(
                    account_id=linkedin_account.account_id,
                    conversation_id=conversation_id,
                    message=validated_message
                )
            except Exception:
                # If sending into an existing chat fails and we have no chat, try starting one by attendee
                logger.info("Falling back to starting chat with attendee via /chats API")
                result = unipile.start_chat_with_attendee(
                    account_id=linkedin_account.account_id,
                    attendee_provider_id=lead.provider_id,
                    text=validated_message
                )
            
            logger.info(f"Unipile message result: {result}")
            
            # Update lead status
            lead.last_step_sent_at = datetime.utcnow()
            lead.current_step = (lead.current_step or 0) + 1
            
            # Create event record
            event = Event(
                lead_id=lead.id,
                event_type='message_sent',
                meta_json={
                    'message': message,
                    'linkedin_account_id': linkedin_account.id,
                    'unipile_result': result
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Message sent to lead {lead.id}")
            
            return {
                'success': True,
                'message': 'Message sent successfully',
                'unipile_result': result
            }
            
        except Exception as e:
            logger.error(f"Error sending message to lead {lead.id}: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_sequence(self, sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a sequence definition."""
        try:
            errors = []
            
            if not sequence:
                errors.append("Sequence cannot be empty")
                return {'valid': False, 'errors': errors}
            
            for i, step in enumerate(sequence):
                # Check required fields
                if 'step_order' not in step:
                    errors.append(f"Step {i+1}: step_order is required")
                if 'action_type' not in step:
                    errors.append(f"Step {i+1}: action_type is required")
                if 'message' not in step:
                    errors.append(f"Step {i+1}: message is required")
                
                # Validate action types
                if 'action_type' in step:
                    valid_actions = ['connection_request', 'message']
                    if step['action_type'] not in valid_actions:
                        errors.append(f"Step {i+1}: Invalid action_type. Must be one of {valid_actions}")
                
                # Validate step order
                if 'step_order' in step:
                    if not isinstance(step['step_order'], int) or step['step_order'] < 1:
                        errors.append(f"Step {i+1}: step_order must be a positive integer")
            
            # Check for duplicate step orders
            step_orders = [step.get('step_order') for step in sequence if 'step_order' in step]
            if len(step_orders) != len(set(step_orders)):
                errors.append("Duplicate step_order values found")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating sequence: {str(e)}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"]
            }
    
    def process_connection_accepted(self, lead: Lead):
        """Process when a connection request is accepted."""
        try:
            logger.info(f"Processing connection acceptance for lead {lead.id}")
            
            # Update lead status to connected
            lead.status = 'connected'
            db.session.commit()
            
            # Check if there's a next step (message) that can be sent immediately
            next_step = self.get_next_step_for_lead(lead)
            if next_step and next_step['action_type'] == 'message':
                logger.info(f"Connection accepted for lead {lead.id} - ready for immediate message")
                # The lead will be processed in the next automation cycle
            else:
                logger.info(f"Connection accepted for lead {lead.id} - no immediate next step")
            
        except Exception as e:
            logger.error(f"Error processing connection acceptance for lead {lead.id}: {str(e)}")
            db.session.rollback()
    
    def validate_sequence_definition(self, sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a sequence definition (alias for validate_sequence)."""
        return self.validate_sequence(sequence)

