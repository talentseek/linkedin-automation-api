"""
Lead processing and step execution functionality.

This module contains functionality for:
- Lead processing logic
- Step execution
- Delay calculations
- Lead readiness checking
"""

import logging
import random
from datetime import datetime, timedelta
from src.models import db, Lead, LinkedInAccount, Campaign, Event
from src.services.unipile_client import UnipileClient

logger = logging.getLogger(__name__)


def _is_lead_ready_for_processing(self, lead):
    """Check if a lead is ready for processing."""
    try:
        # Get the campaign
        campaign = Campaign.query.get(lead.campaign_id)
        if not campaign or campaign.status != 'active':
            return False
        
        # Get the LinkedIn account
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            logger.warning(f"No connected LinkedIn account for campaign {campaign.id}")
            return False
        
        # Check if lead is in a processable status
        if lead.status not in ['pending_invite', 'connected', 'messaged']:
            return False
        
        # Check if enough time has passed since last step
        if lead.last_step_sent_at:
            time_since_last_step = datetime.utcnow() - lead.last_step_sent_at
            required_delay = self._get_required_delay_for_step(lead.current_step)
            
            if time_since_last_step.total_seconds() < required_delay:
                return False
        
        # Check rate limits
        if lead.status == 'pending_invite':
            if not self._can_send_invite_for_account(linkedin_account.account_id):
                logger.info(f"Rate limit reached for invites on account {linkedin_account.account_id}")
                return False
        else:
            is_first_level = lead.connection_type == '1st Level'
            if not self._can_send_message_for_account(linkedin_account.account_id, is_first_level):
                logger.info(f"Rate limit reached for messages on account {linkedin_account.account_id}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking lead readiness: {str(e)}")
        return False


def _process_single_lead(self, lead):
    """Process a single lead."""
    try:
        logger.info(f"Processing lead {lead.id} (status: {lead.status})")
        
        # Get the campaign and LinkedIn account
        campaign = Campaign.query.get(lead.campaign_id)
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            logger.error(f"No LinkedIn account found for lead {lead.id}")
            return
        
        # Get sequence engine
        sequence_engine = self._get_sequence_engine()
        
        # Get the next step
        sequence = campaign.sequence_json
        if not sequence or not isinstance(sequence, list):
            logger.error(f"Invalid sequence for campaign {campaign.id}")
            return
        
        next_step_index = lead.current_step
        if next_step_index >= len(sequence):
            logger.info(f"Lead {lead.id} has completed all steps")
            lead.status = 'completed'
            db.session.commit()
            return
        
        next_step = sequence[next_step_index]
        
        # Execute the step
        try:
            result = sequence_engine.execute_step(lead, next_step, linkedin_account)
            
            if result.get('success'):
                # Update lead status and step
                lead.current_step += 1
                lead.last_step_sent_at = datetime.utcnow()
                
                # Update status based on action type
                action_type = next_step.get('action_type')
                if action_type == 'invite':
                    lead.status = 'invite_sent'
                    self._increment_usage(linkedin_account.account_id, 'connection')
                elif action_type == 'message':
                    lead.status = 'messaged'
                    self._increment_usage(linkedin_account.account_id, 'message')
                
                # Create event
                event = Event(
                    event_type=f'step_{action_type}_sent',
                    lead_id=lead.id,
                    meta_json={
                        'step_index': next_step_index,
                        'step_data': next_step,
                        'result': result
                    }
                )
                
                db.session.add(event)
                db.session.commit()
                
                logger.info(f"Successfully executed step {next_step_index} for lead {lead.id}")
                
            else:
                logger.error(f"Failed to execute step for lead {lead.id}: {result.get('error')}")
                lead.status = 'error'
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error executing step for lead {lead.id}: {str(e)}")
            lead.status = 'error'
            db.session.commit()
        
    except Exception as e:
        logger.error(f"Error processing lead {lead.id}: {str(e)}")
        db.session.rollback()


def _get_step_number(self, lead, next_step):
    """Get the step number for display purposes."""
    try:
        return lead.current_step + 1
    except Exception as e:
        logger.error(f"Error getting step number: {str(e)}")
        return 1


def _get_required_delay_for_step(self, step_number):
    """Get the required delay for a specific step."""
    try:
        # Base delay is 3 working days (in seconds)
        base_delay = 3 * 24 * 60 * 60  # 3 days in seconds
        
        # For the first step (step 0), no delay
        if step_number == 0:
            return 0
        
        # For subsequent steps, use the base delay
        return base_delay
        
    except Exception as e:
        logger.error(f"Error calculating delay: {str(e)}")
        return 24 * 60 * 60  # Default to 1 day
