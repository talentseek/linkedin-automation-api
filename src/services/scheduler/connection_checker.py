"""
Connection and invitation checking functionality.

This module contains functionality for:
- Checking account relations
- Checking sent invitations
- Processing new connections
"""

import logging
from datetime import datetime
from src.models import db, Lead, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient

logger = logging.getLogger(__name__)


def _check_single_account_relations(account_id, unipile):
    """Check relations for a single account and process new connections."""
    try:
        logger.info(f"Checking relations for account: {account_id}")
        
        # Get relations from Unipile
        relations = unipile.get_relations(account_id=account_id)
        
        if not relations:
            logger.info(f"No relations found for account {account_id}")
            return
        
        logger.info(f"Found {len(relations)} relations for account {account_id}")
        
        # Process each relation
        for relation in relations:
            try:
                # Check if relation is a dictionary
                if not isinstance(relation, dict):
                    logger.warning(f"Invalid relation format (expected dict, got {type(relation)}): {relation}")
                    continue
                _process_relation(relation, account_id)
            except Exception as e:
                logger.error(f"Error processing relation: {str(e)}")
                continue
        
        # Also check sent invitations
        _check_sent_invitations(account_id, unipile)
        
    except Exception as e:
        logger.error(f"Error checking relations for account {account_id}: {str(e)}")


def _process_relation(relation, account_id):
    """Process a single relation."""
    try:
        # Extract relation data
        user_provider_id = relation.get('user_provider_id')
        user_full_name = relation.get('user_full_name')
        user_public_identifier = relation.get('user_public_identifier')
        
        if not user_provider_id:
            logger.warning("Relation missing user_provider_id")
            return
        
        # Find lead by provider_id
        lead = Lead.query.filter_by(provider_id=user_provider_id).first()
        
        if not lead:
            logger.info(f"No lead found for provider_id: {user_provider_id}")
            return
        
        # Update lead status if needed
        if lead.status in ['invite_sent', 'invited']:
            old_status = lead.status
            lead.status = 'connected'
            lead.connected_at = datetime.utcnow()
            
            # Create event
            event = Event(
                event_type='connection_accepted',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'user_provider_id': user_provider_id,
                    'user_full_name': user_full_name,
                    'user_public_identifier': user_public_identifier,
                    'detection_method': 'periodic_check',
                    'relation_data': relation
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} connected via periodic check: {old_status} -> connected")
            
    except Exception as e:
        logger.error(f"Error processing relation: {str(e)}")
        db.session.rollback()


def _check_sent_invitations(account_id, unipile):
    """Check sent invitations and update lead statuses."""
    try:
        logger.info(f"Checking sent invitations for account: {account_id}")
        
        # Get sent invitations from Unipile
        invitations = unipile.get_sent_invitations(account_id=account_id)
        
        if not invitations:
            logger.info(f"No sent invitations found for account {account_id}")
            return
        
        logger.info(f"Found {len(invitations)} sent invitations for account {account_id}")
        
        # Process each invitation
        for invitation in invitations:
            try:
                _process_sent_invitation(invitation, account_id)
            except Exception as e:
                logger.error(f"Error processing invitation: {str(e)}")
                continue
        
    except Exception as e:
        logger.error(f"Error checking sent invitations for account {account_id}: {str(e)}")


def _process_sent_invitation(invitation, account_id):
    """Process a single sent invitation."""
    try:
        # Extract invitation data
        user_provider_id = invitation.get('user_provider_id')
        user_full_name = invitation.get('user_full_name')
        user_public_identifier = invitation.get('user_public_identifier')
        invitation_status = invitation.get('status')
        
        if not user_provider_id:
            logger.warning("Invitation missing user_provider_id")
            return
        
        # Find lead by provider_id
        lead = Lead.query.filter_by(provider_id=user_provider_id).first()
        
        if not lead:
            logger.info(f"No lead found for provider_id: {user_provider_id}")
            return
        
        # Update lead status based on invitation status
        if invitation_status == 'accepted' and lead.status in ['invite_sent', 'invited']:
            old_status = lead.status
            lead.status = 'connected'
            lead.connected_at = datetime.utcnow()
            
            # Create event
            event = Event(
                event_type='connection_accepted',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'user_provider_id': user_provider_id,
                    'user_full_name': user_full_name,
                    'user_public_identifier': user_public_identifier,
                    'detection_method': 'invitation_check',
                    'invitation_data': invitation
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} connected via invitation check: {old_status} -> connected")
            
        elif invitation_status == 'pending' and lead.status == 'pending_invite':
            old_status = lead.status
            lead.status = 'invite_sent'
            
            # Create event
            event = Event(
                event_type='invite_sent',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'user_provider_id': user_provider_id,
                    'user_full_name': user_full_name,
                    'user_public_identifier': user_public_identifier,
                    'detection_method': 'invitation_check',
                    'invitation_data': invitation
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} invite sent via invitation check: {old_status} -> invite_sent")
        
    except Exception as e:
        logger.error(f"Error processing invitation: {str(e)}")
        db.session.rollback()
