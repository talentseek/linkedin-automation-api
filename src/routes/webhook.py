import hashlib
import hmac
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from src.models import db, Lead, LinkedInAccount, Event
from src.services.scheduler import get_outreach_scheduler
from datetime import datetime

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)


def verify_webhook_signature(payload_body, signature_header, secret):
    """
    Verify that the webhook request came from Unipile.
    
    Args:
        payload_body: Raw request body
        signature_header: Signature from request header
        secret: Webhook secret
    
    Returns:
        bool: True if signature is valid
    """
    if not signature_header or not secret:
        return False
    
    try:
        # Create expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(f"sha256={expected_signature}", signature_header)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {str(e)}")
        return False


@webhook_bp.route('/unipile/users', methods=['POST'])
def handle_users_webhook():
    """Handle webhooks from Unipile for user events (like connection acceptances)."""
    try:
        # Verify webhook signature (temporarily disabled for testing)
        # if not verify_webhook_signature(request):
        #     logger.warning("Invalid webhook signature - but continuing for testing")
        #     # return jsonify({'error': 'Invalid signature'}), 401
        
        payload = request.get_json()
        logger.info(f"Received users webhook: {payload}")
        
        # Handle new relation event (connection acceptance)
        if payload.get('event') == 'new_relation':
            handle_new_relation_event(payload)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error handling users webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/messaging', methods=['POST'])
def handle_messaging_webhook():
    """Handle Unipile messaging webhook events (messages received, etc.)."""
    try:
        # Get raw payload for signature verification
        payload_body = request.get_data()
        signature_header = request.headers.get('X-Unipile-Signature')
        secret = current_app.config.get('UNIPILE_WEBHOOK_SECRET')
        
        # Verify webhook signature (disabled for local testing)
        if secret and not verify_webhook_signature(payload_body, signature_header, secret):
            logger.warning("Invalid webhook signature - but continuing for testing")
            # return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse JSON payload
        try:
            payload = request.get_json()
        except Exception as e:
            logger.error(f"Error parsing webhook JSON: {str(e)}")
            return jsonify({'error': 'Invalid JSON'}), 400
        
        if not payload:
            return jsonify({'error': 'Empty payload'}), 400
        
        event_type = payload.get('type')
        logger.info(f"Received messaging webhook: {event_type}")
        
        if event_type == 'message_received':
            return handle_message_received_event(payload)
        else:
            logger.info(f"Unhandled messaging webhook event type: {event_type}")
            return jsonify({'message': 'Event received but not processed'}), 200
        
    except Exception as e:
        logger.error(f"Error handling messaging webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_new_relation_event(payload):
    """Handle new relation event (connection acceptance)."""
    try:
        # Extract data from the correct payload structure
        account_id = payload.get('account_id')
        user_provider_id = payload.get('user_provider_id')
        user_full_name = payload.get('user_full_name')
        
        logger.info(f"Processing new relation: account_id={account_id}, user_provider_id={user_provider_id}")
        
        # Find the LinkedIn account
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if not linkedin_account:
            logger.error(f"LinkedIn account not found for account_id: {account_id}")
            return
        
        # Find the lead by provider_id
        lead = Lead.query.filter_by(provider_id=user_provider_id).first()
        if not lead:
            logger.warning(f"Lead not found for provider_id: {user_provider_id}")
            return
        
        # Update lead status to connected
        if lead.status in ['invite_sent', 'invited']:
            lead.status = 'connected'
            lead.connected_at = datetime.utcnow()
            
            # Try to get conversation ID from Unipile
            try:
                from src.services.unipile_client import UnipileClient
                unipile = UnipileClient()
                
                # Find conversation robustly
                conversation_id = unipile.find_conversation_with_provider(account_id, user_provider_id)
                
                if conversation_id:
                    lead.conversation_id = conversation_id
                    logger.info(f"Found conversation ID {conversation_id} for lead {lead.id}")
                else:
                    logger.warning(f"Could not find conversation ID for lead {lead.id}")
                    
            except Exception as e:
                logger.error(f"Error getting conversation ID for lead {lead.id}: {str(e)}")
            
            # Create event record
            event = Event(
                event_type='connection_accepted',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'user_provider_id': user_provider_id,
                    'user_full_name': user_full_name,
                    'conversation_id': lead.conversation_id,
                    'webhook_payload': payload
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Successfully updated lead {lead.id} to connected status")
            
            # Trigger next step in sequence if automation is active
            from src.models import Campaign
            campaign = Campaign.query.get(lead.campaign_id)
            if campaign and campaign.status == 'active':
                from src.services.scheduler import get_outreach_scheduler
                scheduler = get_outreach_scheduler()
                if scheduler:
                    # Schedule the next message step
                    scheduler.schedule_lead_step(lead.id, linkedin_account.id)
                    logger.info(f"Scheduled next step for lead {lead.id}")
        
    except Exception as e:
        logger.error(f"Error handling new relation event: {str(e)}")
        db.session.rollback()


def handle_message_received_event(payload):
    """
    Handle message_received webhook event (reply received).
    
    This event is triggered when someone replies to a message.
    """
    try:
        account_info = payload.get('account_info', {})
        message_data = payload.get('data', {})
        
        account_id = account_info.get('account_id')
        if not account_id:
            logger.error("No account_id in message_received webhook")
            return jsonify({'error': 'Missing account_id'}), 400
        
        # Find the LinkedIn account
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if not linkedin_account:
            logger.warning(f"LinkedIn account not found for account_id: {account_id}")
            return jsonify({'message': 'Account not found'}), 200
        
        # Extract sender information
        sender = message_data.get('sender', {})
        sender_provider_id = sender.get('attendee_provider_id')
        
        # Check if this is an incoming message (not sent by our account)
        our_user_id = account_info.get('user_id')
        if sender_provider_id == our_user_id:
            # This is a message sent by our account, ignore it
            logger.debug("Ignoring outgoing message webhook")
            return jsonify({'message': 'Outgoing message ignored'}), 200
        
        if not sender_provider_id:
            logger.error("No sender provider_id in message_received webhook")
            return jsonify({'error': 'Missing sender provider_id'}), 400
        
        # Find the lead with this provider_id
        lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
        if not lead:
            logger.info(f"No lead found for sender provider_id: {sender_provider_id}")
            # This might be a message from someone not in our campaigns
            return jsonify({'message': 'Lead not found'}), 200
        
        # Update lead status to responded (stop automation)
        if lead.status not in ['responded', 'completed']:
            old_status = lead.status
            lead.status = 'responded'
            
            # Create event record
            event = Event(
                lead_id=lead.id,
                event_type='message_received',
                meta_json={
                    'sender_provider_id': sender_provider_id,
                    'account_id': account_id,
                    'message_data': message_data,
                    'webhook_payload': payload,
                    'previous_status': old_status
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            # Use sequence engine to process reply
            sequence_engine = get_outreach_scheduler()._get_sequence_engine()
            sequence_engine.process_lead_replied(lead)
            
            logger.info(f"Lead {lead.id} replied - status updated from {old_status} to responded")
            
            return jsonify({
                'message': 'Reply received event processed',
                'lead_id': lead.id,
                'previous_status': old_status,
                'new_status': lead.status
            }), 200
        else:
            logger.info(f"Lead {lead.id} replied but status was already {lead.status}")
            return jsonify({'message': 'Reply received but lead status unchanged'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error handling message_received event: {str(e)}")
        return jsonify({'error': 'Error processing message event'}), 500


def handle_account_status_event(payload):
    """
    Handle account_status webhook event (account connection status changes).
    
    This event is triggered when a LinkedIn account's connection status changes.
    """
    try:
        account_info = payload.get('account_info', {})
        status_data = payload.get('data', {})
        
        account_id = account_info.get('account_id')
        if not account_id:
            logger.error("No account_id in account_status webhook")
            return jsonify({'error': 'Missing account_id'}), 400
        
        # Find the LinkedIn account
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if not linkedin_account:
            logger.warning(f"LinkedIn account not found for account_id: {account_id}")
            return jsonify({'message': 'Account not found'}), 200
        
        # Extract status information
        new_status = status_data.get('status')
        if not new_status:
            logger.error("No status in account_status webhook data")
            return jsonify({'error': 'Missing status'}), 400
        
        # Map Unipile status to our status
        status_mapping = {
            'OK': 'connected',
            'CREDENTIALS': 'needs_reconnection',
            'DISABLED': 'disabled',
            'ERROR': 'error'
        }
        
        mapped_status = status_mapping.get(new_status, 'unknown')
        old_status = linkedin_account.status
        
        # Update LinkedIn account status
        linkedin_account.status = mapped_status
        
        # Create event record
        event = Event(
            lead_id=None,  # This is an account-level event
            event_type='account_status_changed',
            meta_json={
                'account_id': account_id,
                'linkedin_account_id': linkedin_account.id,
                'old_status': old_status,
                'new_status': mapped_status,
                'unipile_status': new_status,
                'webhook_payload': payload
            }
        )
        
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"LinkedIn account {linkedin_account.id} status updated from {old_status} to {mapped_status}")
        
        return jsonify({
            'message': 'Account status event processed',
            'linkedin_account_id': linkedin_account.id,
            'old_status': old_status,
            'new_status': mapped_status
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error handling account_status event: {str(e)}")
        return jsonify({'error': 'Error processing account status event'}), 500


@webhook_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook functionality."""
    try:
        payload = request.get_json()
        logger.info(f"Test webhook received: {payload}")
        
        return jsonify({
            'message': 'Test webhook received successfully',
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/status', methods=['GET'])
def get_status():
    """Get current status of leads and webhook events.
    Optional query params (no auth):
      - campaign_id
      - campaign_name (defaults to 'Y Meadows Manufacturing Outreach' when omitted)
    """
    try:
        from src.models import Lead, Event, Campaign
        
        # Resolve campaign by id or name
        campaign_id = request.args.get('campaign_id')
        campaign_name = request.args.get('campaign_name', 'Y Meadows Manufacturing Outreach')
        if campaign_id:
            campaign = Campaign.query.get(campaign_id)
        else:
            campaign = Campaign.query.filter_by(name=campaign_name).first()
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        leads = Lead.query.filter_by(campaign_id=campaign.id).all()
        
        # Group leads by status
        status_counts = {}
        for lead in leads:
            status = lead.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        # Get recent events (limit 10) for this campaign only
        recent_events = (
            Event.query.join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id)
            .order_by(Event.timestamp.desc())
            .limit(10)
            .all()
        )
        
        events_data = []
        for event in recent_events:
            events_data.append({
                'id': event.id,
                'event_type': event.event_type,
                'lead_id': event.lead_id,
                'timestamp': event.timestamp.isoformat() if event.timestamp else None,
                'meta_json': event.meta_json
            })
        
        return jsonify({
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'campaign_status': campaign.status,
            'total_leads': len(leads),
            'lead_status_counts': status_counts,
            'recent_events': events_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug/leads', methods=['GET'])
def debug_leads():
    """Debug endpoint to show detailed lead information."""
    try:
        # Gate behind config
        if not current_app.config.get('DEBUG_ENDPOINTS_ENABLED', False):
            return jsonify({'error': 'Not available'}), 404
        from src.models import Lead, Campaign
        
        # Get campaign leads
        campaign = Campaign.query.filter_by(name="Y Meadows Manufacturing Outreach").first()
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        leads = Lead.query.filter_by(campaign_id=campaign.id).all()
        
        # Get sample leads from each status
        connected_leads = Lead.query.filter_by(campaign_id=campaign.id, status='connected').limit(5).all()
        invite_sent_leads = Lead.query.filter_by(campaign_id=campaign.id, status='invite_sent').limit(5).all()
        
        def lead_to_dict(lead):
            return {
                'id': lead.id,
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'full_name': lead.full_name,
                'status': lead.status,
                'provider_id': lead.provider_id,
                'company_name': lead.company_name,
                'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None,
                'current_step': lead.current_step,
                'created_at': lead.created_at.isoformat() if lead.created_at else None
            }
        
        return jsonify({
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'total_leads': len(leads),
            'connected_count': len([l for l in leads if l.status == 'connected']),
            'invite_sent_count': len([l for l in leads if l.status == 'invite_sent']),
            'sample_connected_leads': [lead_to_dict(lead) for lead in connected_leads],
            'sample_invite_sent_leads': [lead_to_dict(lead) for lead in invite_sent_leads]
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug leads: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug/accounts', methods=['GET'])
def debug_accounts():
    """Debug endpoint to show LinkedIn accounts in the database."""
    try:
        if not current_app.config.get('DEBUG_ENDPOINTS_ENABLED', False):
            return jsonify({'error': 'Not available'}), 404
        from src.models import LinkedInAccount
        
        accounts = LinkedInAccount.query.all()
        
        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'account_id': account.account_id,
                'status': account.status,
                'connected_at': account.connected_at.isoformat() if account.connected_at else None
            })
        
        return jsonify({
            'total_accounts': len(accounts),
            'accounts': accounts_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug accounts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug/test-account-lookup', methods=['POST'])
def debug_test_account_lookup():
    """Debug endpoint to test account lookup logic."""
    try:
        from src.models import LinkedInAccount, Lead
        
        payload = request.get_json()
        account_info = payload.get('account_info', {})
        relation_data = payload.get('data', {})
        
        account_id = account_info.get('account_id')
        provider_id = relation_data.get('provider_id')
        
        # Test account lookup
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        
        # Test lead lookup
        lead = Lead.query.filter_by(provider_id=provider_id).first()
        
        return jsonify({
            'account_id_requested': account_id,
            'provider_id_requested': provider_id,
            'account_found': linkedin_account is not None,
            'account_details': linkedin_account.to_dict() if linkedin_account else None,
            'lead_found': lead is not None,
            'lead_details': lead.to_dict() if lead else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug test account lookup: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/reset-leads', methods=['POST'])
def reset_leads():
    """Reset all leads back to invite_sent status for proper webhook testing."""
    try:
        from src.models import Lead, Campaign
        
        # Get campaign leads
        campaign = Campaign.query.filter_by(name="Y Meadows Manufacturing Outreach").first()
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Reset all leads to invite_sent status
        leads_to_reset = Lead.query.filter_by(campaign_id=campaign.id, status='connected').all()
        
        reset_count = 0
        for lead in leads_to_reset:
            lead.status = 'invite_sent'
            reset_count += 1
        
        db.session.commit()
        
        # Get updated counts
        all_leads = Lead.query.filter_by(campaign_id=campaign.id).all()
        status_counts = {}
        for lead in all_leads:
            status = lead.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        return jsonify({
            'message': f'Successfully reset {reset_count} leads back to invite_sent status',
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'leads_reset': reset_count,
            'updated_status_counts': status_counts,
            'total_leads': len(all_leads)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting leads: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/register', methods=['POST'])
@jwt_required()
def register_webhook():
    """Register a webhook with Unipile for monitoring LinkedIn connections or messaging.

    Body JSON:
      - webhook_url: string (required)
      - source: "users" | "messaging" (default: "users")
      - name: string (optional)
      - secret: string (optional) -> sent as header X-Unipile-Secret
      - events: list[str] (optional) -> to restrict events for the webhook source
    """
    try:
        from src.services.unipile_client import UnipileClient
        
        # Get the webhook URL from the request
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        source = (data.get('source') or 'users').strip()
        name = data.get('name') or ("LinkedIn Connection Monitor" if source == 'users' else "Messaging Webhook")
        secret = data.get('secret')
        events = data.get('events')
        
        if not webhook_url:
            return jsonify({'error': 'webhook_url is required'}), 400
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Optional additional headers
        extra_headers = {"X-Unipile-Secret": secret} if secret else None

        # Create webhook for selected source
        webhook_response = unipile.create_webhook(
            request_url=webhook_url,
            webhook_type=source,
            name=name,
            headers=extra_headers,
            events=events,
            account_ids=[]
        )
        
        logger.info(f"Webhook registered successfully: {webhook_response}")
        
        return jsonify({
            'message': 'Webhook registered successfully',
            'webhook_id': webhook_response.get('webhook_id') or webhook_response.get('id'),
            'webhook_url': webhook_url
        }), 201
        
    except Exception as e:
        logger.error(f"Error registering webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/list', methods=['GET'])
@jwt_required()
def list_webhooks():
    """List all webhooks registered with Unipile."""
    try:
        from src.services.unipile_client import UnipileClient
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get list of webhooks
        webhooks_response = unipile.list_webhooks()
        
        return jsonify({
            'webhooks': webhooks_response.get('items', []),
            'total': len(webhooks_response.get('items', []))
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing webhooks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/delete/<webhook_id>', methods=['DELETE'])
@jwt_required()
def delete_webhook(webhook_id):
    """Delete a webhook from Unipile."""
    try:
        from src.services.unipile_client import UnipileClient
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Delete the webhook
        response = unipile.delete_webhook(webhook_id)
        
        logger.info(f"Webhook {webhook_id} deleted successfully")
        
        return jsonify({
            'message': 'Webhook deleted successfully',
            'webhook_id': webhook_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/webhooks/fix-messaging', methods=['POST'])
@jwt_required()
def fix_messaging_webhook():
    """Ensure a single correctly configured messaging webhook exists.

    Behavior:
    - Lists existing webhooks
    - Deletes any messaging webhook pointing to the wrong path
    - Creates messaging webhook pointing to /api/webhooks/unipile/messaging
    """
    try:
        from src.services.unipile_client import UnipileClient
        unipile = UnipileClient()

        base_url = request.host_url.rstrip('/')
        correct_url = f"{base_url}/api/webhooks/unipile/messaging"

        listed = unipile.list_webhooks() or {}
        items = listed.get('items', [])

        deleted = []
        for wh in items:
            if wh.get('source') == 'messaging':
                req = wh.get('request_url')
                if not req or not req.endswith('/api/webhooks/unipile/messaging'):
                    try:
                        unipile.delete_webhook(wh.get('id'))
                        deleted.append(wh.get('id'))
                    except Exception:
                        continue

        created = unipile.create_webhook(
            request_url=correct_url,
            webhook_type='messaging',
            name='Messaging Webhook',
            headers=None,
            events=[
                'message_received',
                'message_read',
                'message_reaction',
                'message_edited',
                'message_deleted'
            ],
            account_ids=[]
        )

        return jsonify({
            'deleted': deleted,
            'created': created
        }), 200
    except Exception as e:
        logger.error(f"Error ensuring messaging webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/sync-historical-connections', methods=['POST'])
def sync_historical_connections():
    """Sync historical connections by checking relations against campaign leads."""
    try:
        from src.models import Campaign, Lead, LinkedInAccount, Event
        from src.services.unipile_client import UnipileClient
        from datetime import datetime
        
        # Read optional scoping params
        body = request.get_json(silent=True) or {}
        requested_campaign_id = body.get('campaign_id')
        requested_linkedin_account_id = body.get('linkedin_account_id')

        # Resolve campaign
        if requested_campaign_id:
            campaign = Campaign.query.get(requested_campaign_id)
        else:
            # Fallback: campaign with most invite_sent leads
            campaign = db.session.query(Campaign).join(Lead).filter(
                Lead.status == 'invite_sent'
            ).group_by(Campaign.id).order_by(
                db.func.count(Lead.id).desc()
            ).first()
        
        if not campaign:
            return jsonify({'error': 'No campaign with invite_sent leads found'}), 404
        
        # Resolve LinkedIn account
        if requested_linkedin_account_id:
            linkedin_account = LinkedInAccount.query.get(requested_linkedin_account_id)
        else:
            linkedin_account = LinkedInAccount.query.filter_by(
                client_id=campaign.client_id,
                status='connected'
            ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'No connected LinkedIn account found for this campaign\'s client'}), 404
        
        # Get relevant leads from this campaign (broaden scope)
        target_statuses = ['invite_sent', 'invited', 'pending_invite', 'connected', 'messaged', 'responded']
        leads = Lead.query.filter(
            Lead.campaign_id == campaign.id,
            Lead.status.in_(target_statuses)
        ).all()
        
        if not leads:
            return jsonify({
                'message': 'No eligible leads found for historical sync with current scope',
                'campaign_id': campaign.id,
                'linkedin_account_id': linkedin_account.id,
                'account_id': linkedin_account.account_id
            }), 200
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get current relations for this specific account (paginated)
        try:
            relations = []
            cursor = None
            while True:
                relations_response = unipile.get_relations(linkedin_account.account_id, cursor=cursor, limit=1000)
                items = relations_response.get('items', [])
                relations.extend(items)
                cursor = relations_response.get('cursor')
                if not cursor:
                    break
        except Exception as e:
            logger.error(f"Error getting relations for account {linkedin_account.account_id}: {str(e)}")
            return jsonify({'error': f'Failed to get relations: {str(e)}'}), 500
        
        # Track results
        synced_count = 0
        not_found_count = 0
        matched_relations = []
        debug_mismatches = []
        
        # Check each relation against our leads
        for relation in relations:
            public_identifier = relation.get('public_identifier')
            member_id = relation.get('member_id')
            
            # If public_identifier missing, try to resolve via member_id
            if not public_identifier and member_id:
                try:
                    profile = unipile.get_user_profile_by_member_id(member_id, linkedin_account.account_id)
                    public_identifier = profile.get('public_identifier')
                    # Enrich relation dict for downstream logging
                    relation['public_identifier'] = public_identifier
                except Exception as _:
                    public_identifier = None
            
            # Find matching lead by public_identifier or provider_id
            matching_lead = None
            for lead in leads:
                if lead.public_identifier == public_identifier or lead.provider_id == member_id:
                    matching_lead = lead
                    break
            
            # If no match found by provider_id, try to get public_identifier for leads that don't have it
            if not matching_lead and public_identifier:
                for lead in leads:
                    if not lead.public_identifier and lead.provider_id:
                        try:
                            # Try to get the profile to see if it matches
                            profile_response = unipile.get_user_profile(
                                identifier=lead.provider_id,
                                account_id=linkedin_account.account_id
                            )
                            profile_public_identifier = profile_response.get('public_identifier')
                            if profile_public_identifier == public_identifier:
                                matching_lead = lead
                                # Update the lead with the public_identifier
                                lead.public_identifier = public_identifier
                                logger.info(f"Found matching lead by profile lookup: {lead.id}")
                                break
                        except Exception as e:
                            logger.debug(f"Error getting profile for lead {lead.id}: {str(e)}")
                            continue
            
            if matching_lead:
                # Update lead status
                matching_lead.status = 'connected'
                matching_lead.connected_at = datetime.utcnow()
                
                # Try to get conversation ID for this lead
                try:
                    # Find conversation robustly
                    conversation_id = unipile.find_conversation_with_provider(
                        linkedin_account.account_id, matching_lead.provider_id
                    )
                    
                    if conversation_id:
                        matching_lead.conversation_id = conversation_id
                        logger.info(f"Found conversation ID {conversation_id} for lead {matching_lead.id}")
                    else:
                        logger.warning(f"Could not find conversation ID for lead {matching_lead.id}")
                except Exception as e:
                    logger.error(f"Error getting conversation ID for lead {matching_lead.id}: {str(e)}")
                
                # Create event
                event = Event(
                    event_type='connection_accepted_historical',
                    lead_id=matching_lead.id,
                    meta_json={
                        'account_id': linkedin_account.account_id,
                        'linkedin_account_id': linkedin_account.id,
                        'member_id': member_id,
                        'public_identifier': public_identifier,
                        'conversation_id': matching_lead.conversation_id,
                        'relation_data': relation,
                        'sync_method': 'historical_sync'
                    }
                )
                db.session.add(event)
                # Count a match as synced even if conversation_id not yet found
                synced_count += 1
                matched_relations.append({
                    'public_identifier': public_identifier,
                    'lead_name': f"{matching_lead.first_name} {matching_lead.last_name}",
                    'lead_company': matching_lead.company_name,
                    'conversation_id': matching_lead.conversation_id
                })
            else:
                not_found_count += 1
                # Record detailed mismatch for debugging (limit size)
                if len(debug_mismatches) < 50:
                    debug_mismatches.append({
                        'relation_member_id': member_id,
                        'relation_public_identifier': public_identifier,
                        'lead_candidates_checked': len(leads)
                    })
        
        # Commit changes
        db.session.commit()
        
        # Prepare an unmatched sample for inspection
        unmatched_sample = []
        try:
            max_sample = 10
            for relation in relations:
                if len(unmatched_sample) >= max_sample:
                    break
                ri = relation.get('public_identifier')
                rm = relation.get('member_id')
                # If no lead matched on these identifiers
                found = any(
                    (lead.public_identifier == ri) or (lead.provider_id == rm) for lead in leads
                )
                if not found:
                    unmatched_sample.append({
                        'public_identifier': ri,
                        'member_id': rm
                    })
        except Exception:
            unmatched_sample = []

        return jsonify({
            'message': 'Historical sync completed',
            'campaign_id': campaign.id,
            'linkedin_account_id': linkedin_account.id,
            'account_id': linkedin_account.account_id,
            'total_leads_checked': len(leads),
            'total_relations_found': len(relations),
            'leads_synced': synced_count,
            'relations_not_matched': not_found_count,
            'matched_relations': matched_relations,
            'unmatched_sample': unmatched_sample,
            'debug_mismatches_count': len(debug_mismatches),
            'debug_mismatches_sample': debug_mismatches[:10]
        }), 200
        
    except Exception as e:
        logger.error(f"Error in sync_historical_connections: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-relations', methods=['POST'])
def debug_relations():
    """Debug endpoint to see the structure of relations data."""
    try:
        from src.services.unipile_client import UnipileClient
        from src.models import LinkedInAccount
        
        # Get the first LinkedIn account
        linkedin_account = LinkedInAccount.query.first()
        if not linkedin_account:
            return jsonify({'error': 'No LinkedIn account found'}), 404
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get current relations
        relations_response = unipile.get_relations(linkedin_account.account_id)
        relations = relations_response.get('items', [])
        
        # Return sample relation data
        sample_relation = relations[0] if relations else {}
        
        return jsonify({
            'account_id': linkedin_account.account_id,
            'total_relations': len(relations),
            'sample_relation': sample_relation,
            'sample_relation_keys': list(sample_relation.keys()) if sample_relation else []
        }), 200
        
    except Exception as e:
        logger.error(f"Error debugging relations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug/campaigns', methods=['GET'])
def debug_campaigns():
    """Debug endpoint to see all campaigns and their lead counts."""
    try:
        from src.models import Campaign, Lead
        
        campaigns = Campaign.query.all()
        campaign_data = []
        
        for campaign in campaigns:
            # Count leads by status
            invite_sent_count = Lead.query.filter_by(
                campaign_id=campaign.id,
                status='invite_sent'
            ).count()
            
            connected_count = Lead.query.filter_by(
                campaign_id=campaign.id,
                status='connected'
            ).count()
            
            total_count = Lead.query.filter_by(campaign_id=campaign.id).count()
            
            campaign_data.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'total_leads': total_count,
                'invite_sent_count': invite_sent_count,
                'connected_count': connected_count
            })
        
        return jsonify({
            'campaigns': campaign_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error debugging campaigns: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/test-send-message', methods=['POST'])
def test_send_message():
    """Test endpoint to manually send a message to a specific lead."""
    try:
        from src.models import Lead, LinkedInAccount
        from src.services.unipile_client import UnipileClient
        
        data = request.get_json()
        lead_id = data.get('lead_id')
        test_message = data.get('message', "Hi {first_name}, thanks for connecting! I've been following {company}'s work and would love to learn more about what you're working on. Any chance you'd be open to a quick chat?")
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        # Get the lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get the LinkedIn account for this campaign
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=lead.campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'No connected LinkedIn account found'}), 404
        
        # Format the message with personalization
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        formatted_message = sequence_engine._format_message(test_message, lead)
        
        # For testing, we'll just return the formatted message without actually sending
        # In production, you would use: unipile.send_message(...)
        
        return jsonify({
            'lead_id': lead_id,
            'lead_name': f"{lead.first_name} {lead.last_name}",
            'lead_company': lead.company_name,
            'linkedin_account_id': linkedin_account.id,
            'account_id': linkedin_account.account_id,
            'original_message': test_message,
            'formatted_message': formatted_message,
            'personalization_data': {
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'company_name': lead.company_name
            },
            'note': 'Message formatted successfully. In production, this would be sent via Unipile API.'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test_send_message: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/activate-campaign', methods=['POST'])
def activate_campaign():
    """Debug endpoint to activate the campaign without authentication."""
    try:
        from src.models import Campaign
        
        # Find the main campaign
        campaign = Campaign.query.filter_by(name="Y Meadows Manufacturing Outreach").first()
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Activate the campaign
        campaign.status = 'active'
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign activated successfully',
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'status': campaign.status
        }), 200
        
    except Exception as e:
        logger.error(f"Error activating campaign: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/scheduler-status', methods=['GET'])
def scheduler_status():
    """Debug endpoint to check scheduler status without authentication."""
    try:
        from src.services.scheduler import get_outreach_scheduler
        
        scheduler = get_outreach_scheduler()
        thread_alive = False
        if scheduler and hasattr(scheduler, 'thread') and scheduler.thread is not None:
            try:
                thread_alive = scheduler.thread.is_alive()
            except Exception:
                thread_alive = False
        
        return jsonify({
            'scheduler_running': bool(scheduler and getattr(scheduler, 'running', False)),
            'scheduler_thread_alive': thread_alive,
            'scheduler_started': bool(scheduler and getattr(scheduler, 'running', False)),
            'campaign_active': True
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking scheduler status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-timing', methods=['GET'])
def debug_timing():
    """Debug endpoint to test timing calculations for connected leads."""
    try:
        if not current_app.config.get('DEBUG_ENDPOINTS_ENABLED', False):
            return jsonify({'error': 'Not available'}), 404
        from src.models import Lead, Campaign
        from src.services.scheduler import get_outreach_scheduler
        from datetime import datetime
        
        # Get a connected lead
        lead = Lead.query.filter_by(status='connected').first()
        if not lead:
            return jsonify({'error': 'No connected leads found'}), 404
        
        scheduler = get_outreach_scheduler()
        
        # Test the timing calculation
        is_ready = scheduler._is_lead_ready_for_processing(lead)
        
        # Get detailed timing info
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        next_step = sequence_engine.get_next_step_for_lead(lead)
        can_execute = sequence_engine.can_execute_step(lead, next_step) if next_step else None
        
        # Calculate timing manually
        if lead.last_step_sent_at:
            time_since_last_step = datetime.utcnow() - lead.last_step_sent_at
            time_since_last_step_minutes = time_since_last_step.total_seconds() / 60
        else:
            time_since_last_step_minutes = None
        
        if lead.created_at:
            time_since_creation = datetime.utcnow() - lead.created_at
            time_since_creation_minutes = time_since_creation.total_seconds() / 60
        else:
            time_since_creation_minutes = None
        
        return jsonify({
            'lead_id': lead.id,
            'lead_name': f"{lead.first_name} {lead.last_name}",
            'lead_status': lead.status,
            'lead_current_step': lead.current_step,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
            'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None,
            'time_since_last_step_minutes': time_since_last_step_minutes,
            'time_since_creation_minutes': time_since_creation_minutes,
            'next_step': next_step,
            'can_execute': can_execute,
            'is_ready_for_processing': is_ready
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug_timing: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/get-conversation-ids', methods=['POST'])
def get_conversation_ids():
    """Get conversation IDs for connected leads."""
    try:
        if not current_app.config.get('DEBUG_ENDPOINTS_ENABLED', False):
            return jsonify({'error': 'Not available'}), 404
        from src.models import Lead, LinkedInAccount
        from src.services.unipile_client import UnipileClient
        
        # Get all connected leads
        connected_leads = Lead.query.filter_by(status='connected').all()
        if not connected_leads:
            return jsonify({'error': 'No connected leads found'}), 404
        
        # Get the LinkedIn account - use the one with the correct account_id format
        linkedin_accounts = LinkedInAccount.query.filter_by(status='connected').all()
        linkedin_account = None
        
        # Find the account with a valid Unipile account_id format (should be alphanumeric)
        for account in linkedin_accounts:
            if account.account_id and len(account.account_id) > 10 and not account.account_id.startswith('jon-'):
                linkedin_account = account
                break
        
        if not linkedin_account:
            return jsonify({'error': 'No valid connected LinkedIn account found'}), 404
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get all conversations
        conversations_response = unipile.get_conversations(linkedin_account.account_id)
        conversations = conversations_response.get('items', [])
        
        results = []
        updated_count = 0
        
        for lead in connected_leads:
            try:
                # Find conversation with this user
                conversation_id = None
                for conversation in conversations:
                    participants = conversation.get('participants', [])
                    for participant in participants:
                        if participant.get('provider_id') == lead.provider_id:
                            conversation_id = conversation.get('id')
                            break
                    if conversation_id:
                        break
                
                if conversation_id:
                    # Update the lead with conversation ID
                    lead.conversation_id = conversation_id
                    updated_count += 1
                    results.append({
                        'lead_id': lead.id,
                        'lead_name': f"{lead.first_name} {lead.last_name}",
                        'conversation_id': conversation_id,
                        'status': 'found'
                    })
                else:
                    results.append({
                        'lead_id': lead.id,
                        'lead_name': f"{lead.first_name} {lead.last_name}",
                        'conversation_id': None,
                        'status': 'not_found'
                    })
                    
            except Exception as e:
                logger.error(f"Error processing lead {lead.id}: {str(e)}")
                results.append({
                    'lead_id': lead.id,
                    'lead_name': f"{lead.first_name} {lead.last_name}",
                    'conversation_id': None,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Commit changes
        db.session.commit()
        
        return jsonify({
            'message': f'Processed {len(connected_leads)} leads, updated {updated_count} with conversation IDs',
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_conversation_ids: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/resolve-conversation-ids', methods=['POST'])
@jwt_required()
def resolve_conversation_ids():
    """Resolve and persist conversation IDs for leads without requiring debug flag.

    Body JSON (optional):
      - campaign_id: UUID to scope leads
      - linkedin_account_id: UUID of LinkedInAccount to use for chats lookup
    """
    try:
        from src.models import Lead, LinkedInAccount, Campaign
        from src.services.unipile_client import UnipileClient

        payload = request.get_json(silent=True) or {}
        campaign_id = payload.get('campaign_id')
        linkedin_account_id = payload.get('linkedin_account_id')

        # Determine lead scope
        lead_query = Lead.query
        if campaign_id:
            lead_query = lead_query.filter(Lead.campaign_id == campaign_id)
        # Focus on leads that could have conversations but missing one
        eligible_statuses = ['connected', 'messaged', 'responded']
        lead_query = lead_query.filter(Lead.status.in_(eligible_statuses))
        lead_query = lead_query.filter((Lead.conversation_id.is_(None)) | (Lead.conversation_id == ''))
        leads = lead_query.all()

        if not leads:
            return jsonify({'message': 'No eligible leads without conversation_id found'}), 200

        # Choose LinkedIn account
        if linkedin_account_id:
            linkedin_account = LinkedInAccount.query.get(linkedin_account_id)
        else:
            # If campaign provided, prefer an account for that campaign's client
            if campaign_id:
                camp = Campaign.query.get(campaign_id)
                linkedin_account = LinkedInAccount.query.filter_by(client_id=camp.client_id, status='connected').first() if camp else None
            else:
                linkedin_account = LinkedInAccount.query.filter_by(status='connected').first()

        if not linkedin_account:
            return jsonify({'error': 'No connected LinkedIn account available'}), 404

        unipile = UnipileClient()
        updated = 0
        results = []
        for lead in leads:
            try:
                chat_id = unipile.find_conversation_with_provider(linkedin_account.account_id, lead.provider_id)
                if chat_id:
                    lead.conversation_id = chat_id
                    updated += 1
                    results.append({'lead_id': lead.id, 'public_identifier': lead.public_identifier, 'conversation_id': chat_id, 'status': 'found'})
                else:
                    results.append({'lead_id': lead.id, 'public_identifier': lead.public_identifier, 'conversation_id': None, 'status': 'not_found'})
            except Exception as e:
                results.append({'lead_id': lead.id, 'public_identifier': lead.public_identifier, 'conversation_id': None, 'status': 'error', 'error': str(e)})

        db.session.commit()
        return jsonify({'message': f'Processed {len(leads)} leads', 'updated': updated, 'results': results}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in resolve_conversation_ids: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/debug/send-chat', methods=['POST'])
def debug_send_chat():
    """Debug: send a message to a lead using Unipile chats API with robust fallbacks.

    Body JSON:
      - lead_id: string (required)
      - message: string (optional)
    """
    try:
        if not current_app.config.get('DEBUG_ENDPOINTS_ENABLED', False):
            return jsonify({'error': 'Not available'}), 404
        data = request.get_json(silent=True) or {}
        lead_id = data.get('lead_id')
        text = data.get('message') or "Hi {first_name}, thanks for connecting!"
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400

        from src.models import Lead, LinkedInAccount
        from src.services.unipile_client import UnipileClient
        from src.services.sequence_engine import SequenceEngine

        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404

        # Personalize
        seq = SequenceEngine()
        personalized = seq._format_message(text, lead)

        # Choose the correct LinkedIn account: prefer the one used to send the invite
        from sqlalchemy import desc
        invite_event = Event.query.filter_by(lead_id=lead.id, event_type='connection_request_sent').order_by(desc(Event.timestamp)).first()
        linkedin_account = None
        if invite_event:
            try:
                acct_id = (invite_event.meta_json or {}).get('linkedin_account_id')
                if acct_id:
                    linkedin_account = LinkedInAccount.query.get(acct_id)
            except Exception:
                linkedin_account = None
        if not linkedin_account:
            # Fallback to any connected account
            accounts = LinkedInAccount.query.filter_by(status='connected').all()
            for acct in accounts:
                if acct.account_id and len(acct.account_id) > 10 and not str(acct.account_id).startswith('jon-'):
                    linkedin_account = acct
                    break
            if not linkedin_account and accounts:
                linkedin_account = accounts[0]
        if not linkedin_account:
            return jsonify({'error': 'No connected LinkedIn account found'}), 404

        unipile = UnipileClient()
        method_used = None
        send_result = None
        profile_info = None
        attendee_member_id = None
        # Try to resolve a LinkedIn-friendly attendee identifier (member_id preferred)
        try:
            prof = unipile.get_user_profile(identifier=lead.provider_id, account_id=linkedin_account.account_id)
            profile_info = prof
            attendee_member_id = prof.get('member_id') or prof.get('provider_id')
        except Exception:
            profile_info = None

        # 1) Try existing chat
        chat_id = lead.conversation_id
        if chat_id:
            try:
                send_result = unipile.send_message(linkedin_account.account_id, chat_id, personalized)
                method_used = 'existing_chat_send'
            except Exception as e:
                send_result = {'error': str(e)}

        # 2) Try to find chat (try both provider_id and member_id)
        if not send_result or ('error' in send_result):
            try:
                found_chat = None
                for cand in filter(None, [lead.provider_id, attendee_member_id]):
                    found_chat = unipile.find_conversation_with_provider(linkedin_account.account_id, cand)
                    if found_chat:
                        break
                if found_chat:
                    lead.conversation_id = found_chat
                    db.session.commit()
                    chat_id = found_chat
                    send_result = unipile.send_message(linkedin_account.account_id, chat_id, personalized)
                    method_used = 'found_chat_send'
            except Exception as e:
                send_result = {'error': str(e)}

        # 3) Start new chat
        if not send_result or ('error' in send_result):
            try:
                attendee_for_start = attendee_member_id or lead.provider_id
                send_result = unipile.start_chat_with_attendee(
                    account_id=linkedin_account.account_id,
                    attendee_provider_id=attendee_for_start,
                    text=personalized,
                )
                method_used = 'start_chat_with_attendee'
                new_chat_id = (
                    (send_result.get('chat') or {}).get('id')
                    if isinstance(send_result, dict) and isinstance(send_result.get('chat'), dict)
                    else send_result.get('id') if isinstance(send_result, dict) else None
                )
                if new_chat_id:
                    lead.conversation_id = new_chat_id
                    db.session.commit()
            except Exception as e:
                # Try to surface more information if UnipileAPIError
                err_payload = getattr(e, 'response_data', None)
                return jsonify({'error': f'Failed to send via chats API: {str(e)}', 'provider_error': err_payload}), 500

        return jsonify({
            'lead_id': lead.id,
            'lead_name': f"{lead.first_name} {lead.last_name}",
            'account_id': linkedin_account.account_id,
            'conversation_id': lead.conversation_id,
            'method_used': method_used,
            'personalized_message': personalized,
            'unipile_result': send_result,
            'resolved_profile': profile_info,
            'attendee_member_id': attendee_member_id,
        }), 200

    except Exception as e:
        logger.error(f"Error in debug_send_chat: {str(e)}")
        err_payload = getattr(e, 'response_data', None)
        return jsonify({'error': str(e), 'provider_error': err_payload}), 500

