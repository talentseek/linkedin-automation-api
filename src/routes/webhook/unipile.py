"""
Unipile simple webhook endpoint.

This module contains the unified webhook endpoint that handles all Unipile events.
"""

import logging
import json
from flask import request, jsonify
from src.models import db, WebhookData
from src.routes.webhook import webhook_bp
from datetime import datetime

logger = logging.getLogger(__name__)


@webhook_bp.route('/unipile/simple', methods=['POST'])
def handle_unipile_simple():
    """Simple webhook handler for basic Unipile events."""
    try:
        # Log the simple webhook
        logger.info("Simple Unipile webhook received")
        
        # Get payload
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Empty payload'}), 400
        
        # Store webhook data
        webhook_data = WebhookData(
            method=request.method,
            url=request.url,
            headers=json.dumps(dict(request.headers)),
            raw_data=request.get_data(as_text=True),
            json_data=json.dumps(payload),
            content_type=request.content_type,
            content_length=request.content_length
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        logger.info(f"Simple webhook stored: {webhook_data.id}")
        
        # Process the webhook event
        event_type = payload.get('event') or payload.get('type')
        logger.info(f"Processing event type: {event_type}")
        
        # Route to appropriate handler based on event type
        if event_type == 'new_relation':
            logger.info("Routing to new_relation handler")
            from .handlers import handle_new_relation_webhook
            return handle_new_relation_webhook(payload)
        elif event_type == 'message_received':
            logger.info("Routing to message_received handler")
            from .handlers import handle_message_received_webhook
            return handle_message_received_webhook(payload)
        elif event_type == 'message_read':
            logger.info("Routing to message_read handler (treating as message_received)")
            from .handlers import handle_message_received_webhook
            return handle_message_received_webhook(payload)
        elif event_type == 'account_status':
            logger.info("Routing to account_status handler")
            from .handlers import handle_account_status_webhook
            return handle_account_status_webhook(payload)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            logger.info(f"Full payload for unhandled event: {json.dumps(payload, indent=2)}")
            return jsonify({'message': 'Event received and stored but not processed'}), 200
        
    except Exception as e:
        logger.error(f"Error processing simple webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



