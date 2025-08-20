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
    """Check relations for a single LinkedIn account."""
    logger.info(f"Checking relations for account {account_id}")
    
    # Get relations from Unipile with timeout protection
    try:
        logger.info(f"Fetching relations from Unipile for account {account_id}")
        relations_page = unipile.get_relations(account_id=account_id)
        logger.info(f"Successfully retrieved relations response")
        logger.info(f"Retrieved relations for account {account_id}: {relations_page}")
        
        if not relations_page or not isinstance(relations_page, dict):
            logger.error(f"Invalid relations response for account {account_id}: {relations_page}")
            return
        
        # Parse relations - handle both response structures
        relations_items = []
        cursor = None
        
        if 'relations' in relations_page and 'items' in relations_page['relations']:
            # Old structure: {"relations": {"items": [...], "cursor": "..."}}
            relations_items = relations_page['relations']['items']
            cursor = relations_page['relations'].get('cursor')
        elif 'items' in relations_page:
            # New structure: {"items": [...], "cursor": "..."}
            relations_items = relations_page['items']
            cursor = relations_page.get('cursor')
        else:
            logger.warning(f"Unexpected relations response structure for account {account_id}: {list(relations_page.keys())}")
            return
        
        logger.info(f"Found {len(relations_items)} relations for account {account_id}")
        
        # Process each relation
        for relation in relations_items:
            try:
                _process_relation(relation, account_id)
            except Exception as e:
                logger.error(f"Error processing relation {relation.get('member_id', 'unknown')}: {str(e)}")
                continue
        
        # Handle pagination if there's a cursor
        page_count = 0
        max_pages = 10  # Prevent infinite loops
        
        while cursor and page_count < max_pages:
            try:
                page_count += 1
                logger.info(f"Fetching page {page_count} with cursor: {cursor}")
                relations_page = unipile.get_relations(account_id=account_id, cursor=cursor)
                
                if not relations_page or not isinstance(relations_page, dict):
                    logger.error(f"Invalid paginated relations response: {relations_page}")
                    break
                
                # Parse paginated response
                if 'relations' in relations_page and 'items' in relations_page['relations']:
                    relations_items = relations_page['relations']['items']
                    cursor = relations_page['relations'].get('cursor')
                elif 'items' in relations_page:
                    relations_items = relations_page['items']
                    cursor = relations_page.get('cursor')
                else:
                    logger.warning(f"Unexpected paginated response structure: {list(relations_page.keys())}")
                    break
                
                logger.info(f"Found {len(relations_items)} additional relations")
                
                # Process each relation from this page
                for relation in relations_items:
                    try:
                        _process_relation(relation, account_id)
                    except Exception as e:
                        logger.error(f"Error processing paginated relation {relation.get('member_id', 'unknown')}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error fetching paginated relations: {str(e)}")
                break
        
        if page_count >= max_pages:
            logger.warning(f"Reached maximum page limit ({max_pages}) for account {account_id}")
            
    except Exception as e:
        logger.error(f"Error checking relations for account {account_id}: {str(e)}")
        db.session.rollback()


def _process_relation(relation, account_id):
    """Process a single relation."""
    try:
        logger.info(f"=== PROCESSING RELATION ===")
        
        # Extract relation data using correct field names
        member_id = relation.get('member_id')
        public_identifier = relation.get('public_identifier')
        first_name = relation.get('first_name')
        last_name = relation.get('last_name')
        full_name = f"{first_name} {last_name}".strip() if first_name and last_name else None
        
        logger.info(f"Processing relation: member_id={member_id}, public_identifier={public_identifier}, name={full_name}")
        
        if not member_id and not public_identifier:
            logger.warning("Relation missing both member_id and public_identifier")
            logger.info(f"=== RELATION PROCESSING COMPLETE (no identifiers) ===")
            return
        
        # Find lead by member_id (provider_id) or public_identifier
        lead = None
        logger.info(f"Searching for lead with member_id: {member_id}")
        if member_id:
            lead = Lead.query.filter_by(provider_id=member_id).first()
            if lead:
                logger.info(f"Found lead by member_id: {member_id}")
            else:
                logger.info(f"No lead found by member_id: {member_id}")
        
        if not lead and public_identifier:
            logger.info(f"Searching for lead by public_identifier: {public_identifier}")
            lead = Lead.query.filter_by(public_identifier=public_identifier).first()
            if lead:
                logger.info(f"Found lead by public_identifier: {public_identifier}")
                # Update the lead's provider_id for future matches
                if not lead.provider_id and member_id:
                    lead.provider_id = member_id
                    logger.info(f"Updated lead {lead.id} provider_id to {member_id}")
            else:
                logger.info(f"No lead found for public_identifier: {public_identifier}")
        
        if not lead:
            logger.info(f"No lead found for member_id: {member_id} or public_identifier: {public_identifier}")
            logger.info(f"=== RELATION PROCESSING COMPLETE (no matching lead) ===")
            return
        
        logger.info(f"Processing lead {lead.id} with status: {lead.status}")
        
        # Update lead status if needed
        if lead.status in ['invite_sent', 'invited']:
            logger.info(f"Updating lead {lead.id} status from {lead.status} to connected")
            old_status = lead.status
            lead.status = 'connected'
            lead.connected_at = datetime.utcnow()
            
            # Create event
            event = Event(
                event_type='connection_accepted',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'member_id': member_id,
                    'full_name': full_name,
                    'public_identifier': public_identifier,
                    'detection_method': 'periodic_check',
                    'relation_data': relation
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} connected via periodic check: {old_status} -> connected")
            logger.info(f"=== RELATION PROCESSING COMPLETE (status updated) ===")
        else:
            logger.info(f"Lead {lead.id} status is {lead.status}, not updating")
            logger.info(f"=== RELATION PROCESSING COMPLETE (no status update needed) ===")
            
    except Exception as e:
        logger.error(f"Error processing relation: {str(e)}")
        logger.info(f"=== RELATION PROCESSING COMPLETE (error) ===")
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
