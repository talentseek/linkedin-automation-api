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
    """Verify webhook signature from Unipile."""
    if not signature_header or not secret:
        return False
    
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected_signature}", signature_header)
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


@webhook_bp.route('/unipile/webhook', methods=['POST'])
def handle_unipile_webhook():
    """Unified webhook handler for all Unipile events."""
    try:
        # Log webhook receipt with timestamp
        logger.info("=" * 50)
        logger.info(f"WEBHOOK RECEIVED AT: {datetime.utcnow().isoformat()}")
        logger.info("=" * 50)
        logger.info(f"Request Method: {request.method}")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request Headers: {dict(request.headers)}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.content_length}")
        
        # Get payload
        payload_body = request.get_data()
        logger.info(f"Raw payload body length: {len(payload_body) if payload_body else 0}")
        
        try:
            payload = request.get_json()
            logger.info(f"Parsed JSON payload: {json.dumps(payload, indent=2)}")
        except Exception as json_error:
            logger.error(f"Failed to parse JSON: {str(json_error)}")
            logger.error(f"Raw body: {payload_body}")
            return jsonify({'error': 'Invalid JSON'}), 400
        
        if not payload:
            logger.error("Empty webhook payload")
            return jsonify({'error': 'Empty payload'}), 400
        
        # Basic signature verification (optional)
        secret = current_app.config.get('UNIPILE_WEBHOOK_SECRET')
        signature_header = request.headers.get('X-Unipile-Signature')
        unipile_auth_header = request.headers.get('Unipile-Auth')
        
        # Since Pipedream works without auth headers, accept all webhooks for now
        logger.info("Accepting webhook without signature verification for compatibility")
        
        # Optional: Log if we have signature headers for debugging
        if signature_header:
            logger.info("X-Unipile-Signature header present")
        if unipile_auth_header:
            logger.info("Unipile-Auth header present")
        
        # Route to appropriate handler based on event type
        event_type = payload.get('type') or payload.get('event')
        logger.info(f"EVENT TYPE DETECTED: {event_type}")
        logger.info(f"Available payload keys: {list(payload.keys())}")
        
        if event_type == 'new_relation':
            logger.info("Routing to new_relation handler")
            return handle_new_relation_webhook(payload)
        elif event_type == 'message_received':
            logger.info("Routing to message_received handler")
            return handle_message_received_webhook(payload)
        elif event_type == 'message_read':
            logger.info("Routing to message_read handler (treating as message_received)")
            return handle_message_received_webhook(payload)
        elif event_type == 'account_status':
            logger.info("Routing to account_status handler")
            return handle_account_status_webhook(payload)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            logger.info(f"Full payload for unhandled event: {json.dumps(payload, indent=2)}")
            return jsonify({'message': 'Event received but not processed'}), 200
            
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal error'}), 500
    finally:
        logger.info("=" * 50)
        logger.info("WEBHOOK PROCESSING COMPLETE")
        logger.info("=" * 50)


def handle_new_relation_webhook(payload):
    """Handle new relation webhook (connection acceptance)."""
    try:
        logger.info("Processing new_relation webhook")
        
        # Extract data according to actual Unipile payload structure
        account_id = payload.get('account_id')
        user_provider_id = payload.get('user_provider_id')
        user_full_name = payload.get('user_full_name')
        user_public_identifier = payload.get('user_public_identifier')
        user_profile_url = payload.get('user_profile_url')
        
        logger.info(f"New relation: account={account_id}, user={user_provider_id}, name={user_full_name}")
        logger.info(f"Full payload: {json.dumps(payload, indent=2)}")
        
        # Find lead by provider_id
        lead = Lead.query.filter_by(provider_id=user_provider_id).first()
        
        if not lead:
            logger.warning(f"No lead found for provider_id: {user_provider_id}")
            return jsonify({'message': 'Lead not found'}), 200
        
        # Update lead status
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
                    'user_profile_url': user_profile_url,
                    'detection_method': 'new_relation_webhook',
                    'webhook_payload': payload
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} connected via webhook: {old_status} -> connected")
            
            # Trigger next step
            from src.models import Campaign
            campaign = Campaign.query.get(lead.campaign_id)
            if campaign and campaign.status == 'active':
                scheduler = get_outreach_scheduler()
                if scheduler:
                    scheduler.schedule_lead_step(lead.id, lead.linkedin_account_id)
                    logger.info(f"Scheduled next step for lead {lead.id}")
            
            return jsonify({'message': 'Connection processed'}), 200
        else:
            logger.info(f"Lead {lead.id} already in status: {lead.status}")
            return jsonify({'message': 'Lead status unchanged'}), 200
            
    except Exception as e:
        logger.error(f"Error processing new_relation webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Processing error'}), 500


def handle_message_received_webhook(payload):
    """Handle message received webhook (reply detection)."""
    try:
        logger.info("=" * 30)
        logger.info("PROCESSING message_received webhook")
        logger.info("=" * 30)
        
        # Extract message data according to actual Unipile payload structure
        account_id = payload.get('account_id')
        account_info = payload.get('account_info', {})
        sender = payload.get('sender', {})
        message_text = payload.get('message')
        chat_id = payload.get('chat_id')
        message_id = payload.get('message_id')
        
        # Get sender provider_id from the correct field (based on Pipedream data)
        sender_provider_id = sender.get('attendee_provider_id')
        sender_name = sender.get('attendee_name')
        
        logger.info(f"EXTRACTED DATA:")
        logger.info(f"  account_id: {account_id}")
        logger.info(f"  account_info: {json.dumps(account_info, indent=2)}")
        logger.info(f"  sender: {json.dumps(sender, indent=2)}")
        logger.info(f"  message_text: {message_text}")
        logger.info(f"  chat_id: {chat_id}")
        logger.info(f"  message_id: {message_id}")
        logger.info(f"  sender_provider_id: {sender_provider_id}")
        logger.info(f"  sender_name: {sender_name}")
        
        logger.info(f"Message received: account={account_id}, sender={sender_provider_id}, sender_name={sender_name}, chat={chat_id}, message={message_text}")
        
        # Check if this is a sent message (not a received message)
        our_user_id = account_info.get('user_id')
        if sender_provider_id == our_user_id:
            logger.info(f"Ignoring sent message from our account: {sender_provider_id}")
            return jsonify({'message': 'Sent message ignored'}), 200
        
        # REAL-TIME CONNECTION DETECTION: Check if this is an accepted invitation with note
        # According to Unipile docs: "If your invitation includes a message, accepting the invitation 
        # generates a new chat containing only your invitation message"
        if chat_id and message_text:
            # Check if this looks like an invitation message (contains our standard invitation text)
            invitation_indicators = [
                "I work with CFOs to shorten budget cycles",
                "thought it'd be useful to connect",
                "share a resource we've just launched"
            ]
            
            is_invitation_message = any(indicator.lower() in message_text.lower() for indicator in invitation_indicators)
            
            if is_invitation_message:
                logger.info(f"Potential invitation acceptance detected via message webhook: chat_id={chat_id}, sender={sender_provider_id}")
                
                # Find lead by sender provider_id
                lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
                if lead and lead.status in ['invite_sent', 'invited']:
                    logger.info(f"Connection acceptance confirmed via message webhook for lead {lead.id}")
                    
                    # Update lead status to connected
                    lead.status = 'connected'
                    lead.connected_at = datetime.utcnow()
                    lead.conversation_id = chat_id
                    
                    # Create event record
                    event = Event(
                        event_type='connection_accepted',
                        lead_id=lead.id,
                        meta_json={
                            'account_id': account_id,
                            'user_provider_id': sender_provider_id,
                            'detection_method': 'message_webhook',
                            'chat_id': chat_id,
                            'message_text': message_text,
                            'webhook_payload': payload
                        }
                    )
                    
                    db.session.add(event)
                    db.session.commit()
                    
                    logger.info(f"Successfully updated lead {lead.id} to connected status via message webhook")
                    
                    # Trigger next step in sequence if automation is active
                    from src.models import Campaign
                    campaign = Campaign.query.get(lead.campaign_id)
                    if campaign and campaign.status == 'active':
                        from src.services.scheduler import get_outreach_scheduler
                        scheduler = get_outreach_scheduler()
                        if scheduler:
                            # Schedule the next message step
                            scheduler.schedule_lead_step(lead.id, lead.linkedin_account_id)
                            logger.info(f"Scheduled next step for lead {lead.id} via message webhook")
                    
                    return jsonify({'message': 'Connection acceptance processed via message webhook'}), 200
        
        # Find lead by sender provider_id for regular reply detection
        lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
        
        if not lead:
            logger.warning(f"No lead found for sender: {sender_provider_id}")
            return jsonify({'message': 'Lead not found'}), 200
        
        # Update lead status to responded
        if lead.status not in ['responded', 'completed']:
            old_status = lead.status
            lead.status = 'responded'
            
            # Create event
            event = Event(
                event_type='message_received',
                lead_id=lead.id,
                meta_json={
                    'account_id': account_id,
                    'sender_provider_id': sender_provider_id,
                    'sender_name': sender_name,
                    'message_text': message_text,
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'detection_method': 'message_received_webhook',
                    'webhook_payload': payload,
                    'previous_status': old_status
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} replied via webhook: {old_status} -> responded")
            
            # Send notification
            try:
                from src.services.notifications import notify_lead_replied
                notify_lead_replied(lead, lead.campaign, message_preview=message_text)
            except Exception as e:
                logger.warning(f"Notification failed: {str(e)}")
            
            return jsonify({'message': 'Reply processed'}), 200
        else:
            logger.info(f"Lead {lead.id} already responded: {lead.status}")
            return jsonify({'message': 'Lead already responded'}), 200
            
    except Exception as e:
        logger.error(f"Error processing message_received webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Processing error'}), 500


def handle_account_status_webhook(payload):
    """Handle account status webhook."""
    try:
        logger.info("Processing account_status webhook")
        
        account_id = payload.get('account_id')
        status = payload.get('status')
        
        logger.info(f"Account status: {account_id} -> {status}")
        
        # Update LinkedIn account status
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if linkedin_account:
            old_status = linkedin_account.status
            linkedin_account.status = status
            db.session.commit()
            logger.info(f"Account {account_id} status updated: {old_status} -> {status}")
        
        return jsonify({'message': 'Status updated'}), 200
        
    except Exception as e:
        logger.error(f"Error processing account_status webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Processing error'}), 500


# Add this new endpoint at the top of the file, after the imports

@webhook_bp.route('/unipile/simple', methods=['POST'])
def handle_simple_webhook():
    """Simple webhook handler that captures everything and processes events."""
    try:
        from src.models.webhook_data import WebhookData
        import json
        
        # Get raw data
        raw_data = request.get_data()
        headers = dict(request.headers)
        
        # Try to parse JSON
        try:
            json_data = request.get_json()
        except:
            json_data = None
        
        # Store in database
        webhook_data = WebhookData(
            method=request.method,
            url=request.url,
            headers=json.dumps(headers) if headers else None,
            raw_data=raw_data.decode('utf-8') if raw_data else None,
            json_data=json.dumps(json_data) if json_data else None,
            content_type=request.content_type,
            content_length=request.content_length
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        # STEP 1: Basic event detection
        if json_data and isinstance(json_data, dict):
            event_type = json_data.get('event')
            logger.info(f"Simple webhook: Event type detected: {event_type}")
            
            if event_type == 'message_received':
                logger.info("Simple webhook: Processing message_received event")
                
                # STEP 2: Extract message data
                account_id = json_data.get('account_id')
                account_info = json_data.get('account_info', {})
                sender = json_data.get('sender', {})
                sender_provider_id = sender.get('attendee_provider_id')
                message_text = json_data.get('message')
                chat_id = json_data.get('chat_id')
                
                logger.info(f"Simple webhook: account_id={account_id}, sender_provider_id={sender_provider_id}, message={message_text}")
                
                # STEP 3A: Check if this is an accepted invitation (real-time connection detection)
                our_user_id = account_info.get('user_id')
                if sender_provider_id == our_user_id:
                    logger.info(f"Simple webhook: Ignoring sent message from our account: {sender_provider_id}")
                elif chat_id and message_text:
                    # Check if this looks like an invitation message (contains our standard invitation text)
                    invitation_indicators = [
                        "I work with distributors to automate order processing",
                        "thought it'd be useful to connect",
                        "Would love to connect and share insights"
                    ]
                    
                    is_invitation_message = any(indicator.lower() in message_text.lower() for indicator in invitation_indicators)
                    
                    if is_invitation_message:
                        logger.info(f"Simple webhook: Potential invitation acceptance detected: chat_id={chat_id}, sender={sender_provider_id}")
                        
                        # Find lead by sender provider_id
                        from src.models import Lead
                        lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
                        if lead and lead.status in ['invite_sent', 'invited']:
                            logger.info(f"Simple webhook: Connection acceptance confirmed for lead {lead.id}")
                            
                            # Update lead status to connected
                            lead.status = 'connected'
                            lead.connected_at = datetime.utcnow()
                            lead.conversation_id = chat_id
                            
                            # Create event record
                            from src.models import Event
                            event = Event(
                                event_type='connection_accepted',
                                lead_id=lead.id,
                                meta_json={
                                    'account_id': account_id,
                                    'user_provider_id': sender_provider_id,
                                    'detection_method': 'simple_webhook_message',
                                    'chat_id': chat_id,
                                    'message_text': message_text,
                                    'webhook_data_id': webhook_data.id
                                }
                            )
                            
                            db.session.add(event)
                            db.session.commit()
                            
                            logger.info(f"Simple webhook: Updated lead {lead.id} status to connected via invitation acceptance")
                            return jsonify({'status': 'connection_accepted', 'id': webhook_data.id, 'event_type': event_type, 'lead_id': lead.id}), 200
                
                # STEP 3B: Regular reply detection
                if sender_provider_id:
                    from src.models import Lead
                    lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
                    if lead:
                        logger.info(f"Simple webhook: Found lead {lead.id} for sender {sender_provider_id}")
                        
                        # Update lead status and create event
                        if lead.status not in ['responded', 'completed']:
                            old_status = lead.status
                            lead.status = 'responded'
                            
                            # Create event record
                            from src.models import Event
                            event = Event(
                                event_type='message_received',
                                lead_id=lead.id,
                                meta_json={
                                    'account_id': account_id,
                                    'sender_provider_id': sender_provider_id,
                                    'message_text': message_text,
                                    'detection_method': 'simple_webhook',
                                    'webhook_data_id': webhook_data.id
                                }
                            )
                            
                            db.session.add(event)
                            db.session.commit()
                            
                            logger.info(f"Simple webhook: Updated lead {lead.id} status from {old_status} to responded")
                        else:
                            logger.info(f"Simple webhook: Lead {lead.id} already responded (status: {lead.status})")
                    else:
                        logger.info(f"Simple webhook: No lead found for sender {sender_provider_id}")
                else:
                    logger.info("Simple webhook: No sender_provider_id found in webhook data")
            
            elif event_type == 'new_relation':
                logger.info("Simple webhook: Processing new_relation event")
                
                # STEP 2: Extract relation data
                account_id = json_data.get('account_id')
                user_provider_id = json_data.get('user_provider_id')
                user_full_name = json_data.get('user_full_name')
                user_public_identifier = json_data.get('user_public_identifier')
                user_profile_url = json_data.get('user_profile_url')
                
                logger.info(f"Simple webhook: New relation: account={account_id}, user={user_provider_id}, name={user_full_name}")
                
                # STEP 3: Find lead and update status
                if user_provider_id:
                    from src.models import Lead
                    lead = Lead.query.filter_by(provider_id=user_provider_id).first()
                    
                    if lead and lead.status in ['invite_sent', 'invited']:
                        logger.info(f"Simple webhook: Connection acceptance confirmed for lead {lead.id}")
                        
                        # Update lead status to connected
                        old_status = lead.status
                        lead.status = 'connected'
                        lead.connected_at = datetime.utcnow()
                        
                        # Create event record
                        from src.models import Event
                        event = Event(
                            event_type='connection_accepted',
                            lead_id=lead.id,
                            meta_json={
                                'account_id': account_id,
                                'user_provider_id': user_provider_id,
                                'user_full_name': user_full_name,
                                'user_public_identifier': user_public_identifier,
                                'user_profile_url': user_profile_url,
                                'detection_method': 'simple_webhook_new_relation',
                                'webhook_data_id': webhook_data.id
                            }
                        )
                        
                        db.session.add(event)
                        db.session.commit()
                        
                        logger.info(f"Simple webhook: Updated lead {lead.id} status from {old_status} to connected via new_relation")
                        return jsonify({'status': 'connection_accepted', 'id': webhook_data.id, 'event_type': event_type, 'lead_id': lead.id}), 200
                    elif lead:
                        logger.info(f"Simple webhook: Lead {lead.id} already in status: {lead.status}")
                    else:
                        logger.info(f"Simple webhook: No lead found for provider_id: {user_provider_id}")
                else:
                    logger.info("Simple webhook: No user_provider_id found in new_relation data")
                
        return jsonify({'status': 'received', 'id': webhook_data.id, 'event_type': event_type if 'event_type' in locals() else None}), 200
        
    except Exception as e:
        logger.error(f"Simple webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Keep existing endpoints for backward compatibility
@webhook_bp.route('/unipile/users', methods=['POST'])
def handle_users_webhook():
    """Legacy users webhook - redirects to unified handler."""
    return handle_unipile_webhook()


@webhook_bp.route('/unipile/messaging', methods=['POST'])
def handle_messaging_webhook():
    """Legacy messaging webhook - redirects to unified handler."""
    return handle_unipile_webhook()


# Webhook health check endpoint
@webhook_bp.route('/webhook/health', methods=['GET'])
def webhook_health():
    """Check webhook endpoint health."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': {
            'unified': '/api/webhooks/unipile/webhook',
            'simple': '/api/webhooks/unipile/simple',
            'legacy_users': '/api/webhooks/unipile/users',
            'legacy_messaging': '/api/webhooks/unipile/messaging'
        }
    }), 200


@webhook_bp.route('/webhook/data', methods=['GET'])
def get_webhook_data():
    """Get stored webhook data for analysis."""
    try:
        from src.models.webhook_data import WebhookData
        
        # Get recent webhook data
        webhooks = WebhookData.query.order_by(WebhookData.timestamp.desc()).limit(10).all()
        
        return jsonify({
            'webhooks': [webhook.to_dict() for webhook in webhooks],
            'count': len(webhooks)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting webhook data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/status', methods=['GET'])
def get_status():
    """Get current status of leads and webhook events."""
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


@webhook_bp.route('/check-connections', methods=['POST'])
def check_connections():
    """Manual trigger to check for new connections using all detection methods."""
    try:
        from src.services.scheduler import get_outreach_scheduler
        from src.models.linkedin_account import LinkedInAccount
        
        scheduler = get_outreach_scheduler()
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 500
        
        # Get all connected LinkedIn accounts
        accounts = LinkedInAccount.query.filter_by(status='connected').all()
        
        results = []
        for account in accounts:
            try:
                # Check relations for this account
                scheduler._check_account_relations(account)
                results.append({
                    'account_id': account.account_id,
                    'status': 'checked'
                })
            except Exception as e:
                results.append({
                    'account_id': account.account_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'message': 'Connection detection check completed',
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error in check_connections: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-relations', methods=['POST'])
def debug_relations():
    """Debug endpoint to see the structure of relations data."""
    try:
        from src.services.unipile_client import UnipileClient
        from src.models import LinkedInAccount
        
        data = request.get_json() or {}
        account_id = data.get('account_id')
        
        if account_id:
            # Use specified account_id
            linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
            if not linkedin_account:
                # If account not in database, try to get relations directly from Unipile
                logger.warning(f"LinkedIn account {account_id} not found in database, trying direct Unipile API call")
                try:
                    unipile = UnipileClient()
                    relations_response = unipile.get_relations(account_id)
                    relations = relations_response.get('items', [])
                    
                    # Search for Nimish Shah specifically
                    nimish_relation = None
                    for relation in relations:
                        if relation.get('first_name') == 'Nimish' and relation.get('last_name') == 'Shah':
                            nimish_relation = relation
                            break
                    
                    return jsonify({
                        'account_id': account_id,
                        'total_relations': len(relations),
                        'sample_relation': nimish_relation or relations[0] if relations else {},
                        'sample_relation_keys': list((nimish_relation or relations[0] if relations else {}).keys()),
                        'nimish_found': nimish_relation is not None,
                        'note': 'Account not in database, using direct Unipile API'
                    }), 200
                except Exception as e:
                    return jsonify({'error': f'LinkedIn account not found for account_id: {account_id} and direct API call failed: {str(e)}'}), 404
        else:
            # Get the first LinkedIn account as fallback
            linkedin_account = LinkedInAccount.query.first()
            if not linkedin_account:
                return jsonify({'error': 'No LinkedIn account found'}), 404
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get current relations
        relations_response = unipile.get_relations(linkedin_account.account_id)
        relations = relations_response.get('items', [])
        
        # Search for Nimish Shah specifically
        nimish_relation = None
        for relation in relations:
            if relation.get('first_name') == 'Nimish' and relation.get('last_name') == 'Shah':
                nimish_relation = relation
                break
        
        # Return sample relation data
        sample_relation = nimish_relation or relations[0] if relations else {}
        
        return jsonify({
            'account_id': linkedin_account.account_id,
            'total_relations': len(relations),
            'sample_relation': sample_relation,
            'sample_relation_keys': list(sample_relation.keys()) if sample_relation else [],
            'nimish_found': nimish_relation is not None
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug_relations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-sent-invitations', methods=['POST'])
def debug_sent_invitations():
    """Debug endpoint to check sent invitations for an account."""
    try:
        from src.services.unipile_client import UnipileClient
        from src.models import LinkedInAccount
        
        data = request.get_json() or {}
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({'error': 'account_id is required'}), 400
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get sent invitations for this account
        invitations_response = unipile.get_sent_invitations(account_id)
        if not invitations_response:
            return jsonify({'error': 'Failed to get sent invitations'}), 500
        
        invitations = invitations_response.get('items', [])
        
        # Look for Nimish Shah specifically
        nimish_invitation = None
        for invitation in invitations:
            recipient = invitation.get('recipient', {})
            if recipient.get('first_name') == 'Nimish' and recipient.get('last_name') == 'Shah':
                nimish_invitation = invitation
                break
        
        # Return sample invitation data
        sample_invitation = nimish_invitation or invitations[0] if invitations else {}
        
        return jsonify({
            'account_id': account_id,
            'total_invitations': len(invitations),
            'sample_invitation': sample_invitation,
            'sample_invitation_keys': list(sample_invitation.keys()) if sample_invitation else [],
            'nimish_found': nimish_invitation is not None
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug_sent_invitations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/list', methods=['GET'])
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


@webhook_bp.route('/register', methods=['POST'])
def register_webhook():
    """Register a webhook with Unipile for monitoring LinkedIn connections or messaging."""
    try:
        from src.services.unipile_client import UnipileClient
        
        # Get the webhook URL from the request
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        source = (data.get('source') or 'users').strip()
        name = data.get('name') or ("LinkedIn Connection Monitor" if source == 'users' else "Messaging Webhook")
        secret = data.get('secret') or current_app.config.get('UNIPILE_WEBHOOK_SECRET')
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


@webhook_bp.route('/delete/<webhook_id>', methods=['DELETE'])
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


@webhook_bp.route('/configure-unified', methods=['POST'])
def configure_unified_webhook():
    """Configure the unified webhook endpoint for all events."""
    try:
        from src.services.unipile_client import UnipileClient
        
        # Initialize Unipile client
        unipile = UnipileClient()
        
        # Get base URL - force HTTPS
        base_url = "https://linkedin-automation-api.fly.dev"
        webhook_url = f"{base_url}/api/webhooks/unipile/webhook"
        
        # Delete any existing webhooks first
        try:
            webhooks_response = unipile.list_webhooks()
            existing_webhooks = webhooks_response.get('items', [])
            
            for webhook in existing_webhooks:
                webhook_id = webhook.get('id')
                if webhook_id:
                    try:
                        unipile.delete_webhook(webhook_id)
                        logger.info(f"Deleted existing webhook: {webhook_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete webhook {webhook_id}: {str(e)}")
        except Exception as e:
            logger.warning(f"Error cleaning up existing webhooks: {str(e)}")
        
        # Create unified webhook for users (connections) with proper headers
        users_webhook = unipile.create_webhook(
            request_url=webhook_url,
            webhook_type='users',
            name='Unified LinkedIn Webhook',
            headers=[
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Unipile-Auth", "value": current_app.config.get('UNIPILE_WEBHOOK_SECRET')}
            ],
            events=['new_relation'],
            account_ids=[]
        )
        
        # Create unified webhook for messaging (replies) with proper headers
        messaging_webhook = unipile.create_webhook(
            request_url=webhook_url,
            webhook_type='messaging',
            name='Unified Messaging Webhook',
            headers=[
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Unipile-Auth", "value": current_app.config.get('UNIPILE_WEBHOOK_SECRET')}
            ],
            events=['message_received'],
            account_ids=[]
        )
        
        logger.info("Unified webhook configuration completed with proper headers")
        
        return jsonify({
            'message': 'Unified webhook configuration completed with proper headers',
            'webhook_url': webhook_url,
            'users_webhook_id': users_webhook.get('webhook_id') or users_webhook.get('id'),
            'messaging_webhook_id': messaging_webhook.get('webhook_id') or messaging_webhook.get('id')
        }), 200
        
    except Exception as e:
        logger.error(f"Error configuring unified webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/test', methods=['POST'])
def test_webhook_processing():
    """Test endpoint that simulates the exact webhook data we received."""
    try:
        from src.models.webhook_data import WebhookData
        import json
        
        # Simulate webhook data for Andy Smit (real lead in our database)
        test_data = {
            "event": "message_received",
            "account_id": "DQ50O3PMTKW-HDjVfPveqg",
            "sender": {
                "attendee_provider_id": "ACwAAAH1p9EBc8FArRN2jB0kZpCa7bxghS4u1Tk",
                "attendee_name": "Andy Smit"
            },
            "message": "Test message from Andy Smit",
            "chat_id": "test_chat_123",
            "message_id": "test_message_456"
        }
        
        # Store in database (same as simple webhook)
        webhook_data = WebhookData(
            method="POST",
            url="/api/webhooks/unipile/test",
            headers=json.dumps({"Content-Type": "application/json"}),
            raw_data=json.dumps(test_data),
            json_data=json.dumps(test_data),
            content_type="application/json",
            content_length=len(json.dumps(test_data))
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        # Process the test data (same logic as simple webhook)
        event_type = test_data.get('event')
        logger.info(f"Test webhook: Event type detected: {event_type}")
        
        if event_type == 'message_received':
            logger.info("Test webhook: Processing message_received event")
            
            account_id = test_data.get('account_id')
            sender = test_data.get('sender', {})
            sender_provider_id = sender.get('attendee_provider_id')
            message_text = test_data.get('message')
            
            logger.info(f"Test webhook: account_id={account_id}, sender_provider_id={sender_provider_id}, message={message_text}")
            
            # Find lead by sender provider_id
            if sender_provider_id:
                from src.models import Lead
                lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
                if lead:
                    logger.info(f"Test webhook: Found lead {lead.id} for sender {sender_provider_id}")
                    
                    # Update lead status and create event
                    if lead.status not in ['responded', 'completed']:
                        old_status = lead.status
                        lead.status = 'responded'
                        
                        # Create event record
                        from src.models import Event
                        event = Event(
                            event_type='message_received',
                            lead_id=lead.id,
                            meta_json={
                                'account_id': account_id,
                                'sender_provider_id': sender_provider_id,
                                'message_text': message_text,
                                'detection_method': 'test_webhook',
                                'webhook_data_id': webhook_data.id
                            }
                        )
                        
                        db.session.add(event)
                        db.session.commit()
                        
                        return jsonify({
                            'status': 'success',
                            'message': f'Lead {lead.id} status updated from {old_status} to responded',
                            'webhook_data_id': webhook_data.id,
                            'event_id': event.id
                        }), 200
                    else:
                        return jsonify({
                            'status': 'already_responded',
                            'message': f'Lead {lead.id} already responded (status: {lead.status})',
                            'webhook_data_id': webhook_data.id
                        }), 200
                else:
                    return jsonify({
                        'status': 'no_lead_found',
                        'message': f'No lead found for sender {sender_provider_id}',
                        'webhook_data_id': webhook_data.id
                    }), 200
            else:
                return jsonify({
                    'status': 'no_sender_id',
                    'message': 'No sender_provider_id found in test data',
                    'webhook_data_id': webhook_data.id
                }), 200
        
        return jsonify({
            'status': 'unknown_event',
            'message': f'Unknown event type: {event_type}',
            'webhook_data_id': webhook_data.id
        }), 200
        
    except Exception as e:
        logger.error(f"Test webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/test-connection', methods=['POST'])
def test_connection_detection():
    """Test endpoint that simulates a new_relation event for connection detection."""
    try:
        from src.models.webhook_data import WebhookData
        import json
        
        # Simulate new_relation webhook data for John Demko (has invite_sent status)
        test_data = {
            "event": "new_relation",
            "account_id": "DQ50O3PMTKW-HDjVfPveqg",
            "user_provider_id": "ACwAAAAAVY8BSaMDiyCmhsns1tIx7gUTURHJZ-U",
            "user_full_name": "John Demko",
            "user_public_identifier": "john-demko-123",
            "user_profile_url": "https://linkedin.com/in/john-demko-123"
        }
        
        # Store in database (same as simple webhook)
        webhook_data = WebhookData(
            method="POST",
            url="/api/webhooks/unipile/test-connection",
            headers=json.dumps({"Content-Type": "application/json"}),
            raw_data=json.dumps(test_data),
            json_data=json.dumps(test_data),
            content_type="application/json",
            content_length=len(json.dumps(test_data))
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        # Process the test data (same logic as simple webhook)
        event_type = test_data.get('event')
        logger.info(f"Test connection webhook: Event type detected: {event_type}")
        
        if event_type == 'new_relation':
            logger.info("Test connection webhook: Processing new_relation event")
            
            account_id = test_data.get('account_id')
            user_provider_id = test_data.get('user_provider_id')
            user_full_name = test_data.get('user_full_name')
            
            logger.info(f"Test connection webhook: account_id={account_id}, user_provider_id={user_provider_id}, name={user_full_name}")
            
            # Find lead and update status
            if user_provider_id:
                from src.models import Lead
                lead = Lead.query.filter_by(provider_id=user_provider_id).first()
                
                if lead and lead.status in ['invite_sent', 'invited']:
                    logger.info(f"Test connection webhook: Connection acceptance confirmed for lead {lead.id}")
                    
                    # Update lead status to connected
                    old_status = lead.status
                    lead.status = 'connected'
                    lead.connected_at = datetime.utcnow()
                    
                    # Create event record
                    from src.models import Event
                    event = Event(
                        event_type='connection_accepted',
                        lead_id=lead.id,
                        meta_json={
                            'account_id': account_id,
                            'user_provider_id': user_provider_id,
                            'user_full_name': user_full_name,
                            'detection_method': 'test_connection_webhook',
                            'webhook_data_id': webhook_data.id
                        }
                    )
                    
                    db.session.add(event)
                    db.session.commit()
                    
                    return jsonify({
                        'status': 'connection_accepted',
                        'message': f'Lead {lead.id} status updated from {old_status} to connected',
                        'webhook_data_id': webhook_data.id,
                        'event_id': event.id
                    }), 200
                elif lead:
                    return jsonify({
                        'status': 'already_connected',
                        'message': f'Lead {lead.id} already connected (status: {lead.status})',
                        'webhook_data_id': webhook_data.id
                    }), 200
                else:
                    return jsonify({
                        'status': 'no_lead_found',
                        'message': f'No lead found for provider_id {user_provider_id}',
                        'webhook_data_id': webhook_data.id
                    }), 200
            else:
                return jsonify({
                    'status': 'no_user_id',
                    'message': 'No user_provider_id found in test data',
                    'webhook_data_id': webhook_data.id
                }), 200
        
        return jsonify({
            'status': 'unknown_event',
            'message': f'Unknown event type: {event_type}',
            'webhook_data_id': webhook_data.id
        }), 200
        
    except Exception as e:
        logger.error(f"Test connection webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

