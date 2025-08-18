"""
Connection requests and message sending functionality.

This module contains functionality for:
- Sending connection requests
- Sending messages
- Unipile API integration
- Action result handling
"""

import logging
from datetime import datetime
from typing import Dict, Any
from src.models import db, Lead, Event
from src.services.unipile_client import UnipileClient, UnipileAPIError

logger = logging.getLogger(__name__)


def _send_connection_request(self, lead: Lead, linkedin_account, message: str) -> Dict[str, Any]:
    """Send a connection request to a lead."""
    try:
        # CRITICAL FIX: Validate lead data before sending
        if not lead or not hasattr(lead, 'id'):
            logger.error("Invalid lead object in _send_connection_request")
            return {'success': False, 'error': 'Invalid lead object'}
        
        # Refresh lead data to ensure accuracy
        try:
            db.session.refresh(lead)
            logger.info(f"=== CONNECTION REQUEST VERIFICATION ===")
            logger.info(f"Sending connection request to: {lead.first_name} {lead.last_name} (ID: {lead.id})")
            logger.info(f"Message: {message}")
            logger.info(f"=== END CONNECTION REQUEST VERIFICATION ===")
        except Exception as refresh_error:
            logger.error(f"Failed to refresh lead {lead.id} in _send_connection_request: {str(refresh_error)}")
            return {'success': False, 'error': f'Failed to refresh lead data: {str(refresh_error)}'}
        
        logger.info(f"Sending connection request to lead {lead.id}")
        
        # Validate required data
        if not lead.public_identifier:
            error_msg = "Lead missing public_identifier"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        if not message:
            error_msg = "Connection request message cannot be empty"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        # Get Unipile client
        unipile = self._get_unipile_client()

        # Resolve provider_id first (Unipile expects provider/member id, not vanity public identifier)
        provider_id = None
        try:
            profile = unipile.get_user_profile(lead.public_identifier, linkedin_account.account_id)
            if isinstance(profile, dict):
                provider_id = (
                    profile.get('provider_id')
                    or profile.get('id')
                    or (profile.get('user') or {}).get('provider_id')
                )
        except Exception as resolve_err:
            logger.error(f"Failed to resolve provider id for {lead.public_identifier}: {str(resolve_err)}")
            # fallthrough; provider_id may remain None

        if not provider_id:
            error_msg = "Unable to resolve LinkedIn provider ID for lead"
            logger.error(error_msg)
            # Create error event for observability
            event = Event(
                event_type='connection_request_failed',
                lead_id=lead.id,
                meta_json={
                    'message': message,
                    'error': error_msg,
                    'public_identifier': lead.public_identifier
                }
            )
            db.session.add(event)
            db.session.commit()
            return {'success': False, 'error': error_msg}

        # Send connection request via Unipile with resolved provider_id
        try:
            result = unipile.send_connection_request(
                account_id=linkedin_account.account_id,
                profile_id=provider_id,
                message=message
            )
            
            if result.get('success'):
                # Update lead status
                lead.status = 'invite_sent'
                lead.invite_sent_at = datetime.utcnow()
                
                # Create event
                event = Event(
                    event_type='connection_request_sent',
                    lead_id=lead.id,
                    meta_json={
                        'message': message,
                        'unipile_result': result,
                        'linkedin_account_id': linkedin_account.account_id
                    }
                )
                
                db.session.add(event)
                db.session.commit()
                
                logger.info(f"Connection request sent successfully to lead {lead.id}")
                return {
                    'success': True,
                    'message': 'Connection request sent successfully',
                    'unipile_result': result
                }
            else:
                error_msg = f"Unipile API error: {result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                
                # Create error event
                event = Event(
                    event_type='connection_request_failed',
                    lead_id=lead.id,
                    meta_json={
                        'message': message,
                        'error': error_msg,
                        'unipile_result': result
                    }
                )
                
                db.session.add(event)
                db.session.commit()
                
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Error sending connection request via Unipile: {str(e)}"
            logger.error(error_msg)
            
            # Create error event
            event = Event(
                event_type='connection_request_failed',
                lead_id=lead.id,
                meta_json={
                    'message': message,
                    'error': error_msg
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        logger.error(f"Error in _send_connection_request: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def _send_message(self, lead: Lead, linkedin_account, message: str) -> Dict[str, Any]:
    """Send a message to a lead."""
    try:
        # CRITICAL FIX: Validate lead data before sending
        if not lead or not hasattr(lead, 'id'):
            logger.error("Invalid lead object in _send_message")
            return {'success': False, 'error': 'Invalid lead object'}
        
        # Refresh lead data to ensure accuracy
        try:
            db.session.refresh(lead)
            logger.info(f"=== MESSAGE SENDING VERIFICATION ===")
            logger.info(f"Sending message to: {lead.first_name} {lead.last_name} (ID: {lead.id})")
            logger.info(f"Message: {message}")
            logger.info(f"=== END MESSAGE SENDING VERIFICATION ===")
        except Exception as refresh_error:
            logger.error(f"Failed to refresh lead {lead.id} in _send_message: {str(refresh_error)}")
            return {'success': False, 'error': f'Failed to refresh lead data: {str(refresh_error)}'}
        
        logger.info(f"Sending message to lead {lead.id}")
        
        # Validate required data
        if not lead.conversation_id:
            error_msg = "Lead missing conversation_id"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        if not message:
            error_msg = "Message cannot be empty"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        # Get Unipile client
        unipile = self._get_unipile_client()
        
        # Send message via Unipile
        try:
            # FINAL VALIDATION: Double-check we're sending to the right person
            logger.info(f"=== FINAL MESSAGE VALIDATION ===")
            logger.info(f"About to send message to: {lead.first_name} {lead.last_name} (ID: {lead.id})")
            logger.info(f"Message content: {message}")
            logger.info(f"Conversation ID: {lead.conversation_id}")
            logger.info(f"LinkedIn Account: {linkedin_account.account_id}")
            logger.info(f"=== END FINAL MESSAGE VALIDATION ===")
            
            result = unipile.send_message(
                account_id=linkedin_account.account_id,
                conversation_id=lead.conversation_id,
                message=message
            )
            
            if result.get('success'):
                # Update lead status
                lead.status = 'messaged'
                lead.last_message_sent_at = datetime.utcnow()
                
                # Create event
                event = Event(
                    event_type='message_sent',
                    lead_id=lead.id,
                    meta_json={
                        'message': message,
                        'unipile_result': result,
                        'linkedin_account_id': linkedin_account.account_id,
                        'conversation_id': lead.conversation_id
                    }
                )
                
                db.session.add(event)
                db.session.commit()
                
                logger.info(f"Message sent successfully to lead {lead.id}")
                return {
                    'success': True,
                    'message': 'Message sent successfully',
                    'unipile_result': result
                }
            else:
                error_msg = f"Unipile API error: {result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                
                # Create error event
                event = Event(
                    event_type='message_failed',
                    lead_id=lead.id,
                    meta_json={
                        'message': message,
                        'error': error_msg,
                        'unipile_result': result
                    }
                )
                
                db.session.add(event)
                db.session.commit()
                
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Error sending message via Unipile: {str(e)}"
            logger.error(error_msg)
            
            # Create error event
            event = Event(
                event_type='message_failed',
                lead_id=lead.id,
                meta_json={
                    'message': message,
                    'error': error_msg
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        logger.error(f"Error in _send_message: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def _validate_action_prerequisites(self, lead: Lead, action_type: str) -> Dict[str, Any]:
    """Validate prerequisites for an action."""
    try:
        errors = []
        warnings = []
        
        if action_type == 'connection_request':
            if not lead.public_identifier:
                errors.append("Lead missing public_identifier")
            
            if lead.status not in ['pending_invite']:
                warnings.append(f"Lead status '{lead.status}' may not be appropriate for connection request")
        
        elif action_type == 'message':
            if not lead.conversation_id:
                errors.append("Lead missing conversation_id")
            
            if lead.status not in ['connected', 'messaged']:
                warnings.append(f"Lead status '{lead.status}' may not be appropriate for messaging")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating action prerequisites: {str(e)}")
        return {
            'valid': False,
            'errors': [str(e)],
            'warnings': []
        }


def _get_action_summary(self, lead: Lead, action_type: str) -> Dict[str, Any]:
    """Get a summary of the action to be performed."""
    try:
        summary = {
            'lead_id': lead.id,
            'action_type': action_type,
            'lead_status': lead.status,
            'lead_name': f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
            'company': lead.company_name
        }
        
        if action_type == 'connection_request':
            summary['public_identifier'] = lead.public_identifier
        elif action_type == 'message':
            summary['conversation_id'] = lead.conversation_id
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting action summary: {str(e)}")
        return {
            'lead_id': lead.id if lead else None,
            'action_type': action_type,
            'error': str(e)
        }
