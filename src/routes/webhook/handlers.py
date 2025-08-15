"""
Main webhook event handlers.

This module contains the core webhook event handling functionality:
- Main webhook entry point
- New relation handler (connection acceptance)
- Message received handler (reply detection)
- Account status handler
"""

import hashlib
import hmac
import json
import logging
from flask import request, jsonify, current_app
from src.models import db, Lead, LinkedInAccount, Event
from src.services.scheduler import get_outreach_scheduler
from src.routes.webhook import webhook_bp
from datetime import datetime

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
        
        # Find lead by sender provider_id
        lead = Lead.query.filter_by(provider_id=sender_provider_id).first()
        
        if not lead:
            logger.warning(f"No lead found for sender provider_id: {sender_provider_id}")
            return jsonify({'message': 'Lead not found'}), 200
        
        # Update lead status to responded
        if lead.status in ['connected', 'messaged']:
            old_status = lead.status
            lead.status = 'responded'
            lead.responded_at = datetime.utcnow()
            
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
                    'webhook_payload': payload
                }
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.info(f"Lead {lead.id} responded via webhook: {old_status} -> responded")
            
            # Send notification if enabled
            if current_app.config.get('NOTIFICATIONS_ENABLED', False):
                try:
                    from src.services.notifications import NotificationService
                    notification_service = NotificationService()
                    notification_service.send_reply_notification(lead, message_text)
                    logger.info(f"Sent reply notification for lead {lead.id}")
                except Exception as notif_error:
                    logger.error(f"Failed to send notification: {str(notif_error)}")
            
            return jsonify({'message': 'Reply processed'}), 200
        else:
            logger.info(f"Lead {lead.id} already in status: {lead.status}")
            return jsonify({'message': 'Lead status unchanged'}), 200
            
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
        
        logger.info(f"Account status update: {account_id} -> {status}")
        
        # Update LinkedIn account status
        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if linkedin_account:
            linkedin_account.status = status
            db.session.commit()
            logger.info(f"Updated LinkedIn account {account_id} status to {status}")
        
        return jsonify({'message': 'Account status updated'}), 200
        
    except Exception as e:
        logger.error(f"Error processing account_status webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Processing error'}), 500
