"""
Unipile-specific webhook endpoints.

This module contains endpoints for:
- Unipile webhook management
- Unipile user management
- Unipile messaging
- Simple webhook handling
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
        
        # Store webhook data - temporarily disabled for debugging
        # webhook_data = WebhookData(
        #     method=request.method,
        #     url=request.url,
        #     headers=json.dumps(dict(request.headers)),
        #     raw_data=request.get_data(as_text=True),
        #     json_data=json.dumps(payload),
        #     content_type=request.content_type,
        #     content_length=request.content_length
        # )
        # 
        # db.session.add(webhook_data)
        # db.session.commit()
        
        logger.info(f"Simple webhook received and processed (storage disabled)")
        
        logger.info(f"Simple webhook processed (storage disabled)")
        
        return jsonify({'message': 'Simple webhook processed'}), 200
        
    except Exception as e:
        logger.error(f"Error processing simple webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/users', methods=['POST'])
def handle_unipile_users():
    """Handle Unipile user-related webhooks."""
    try:
        logger.info("Unipile users webhook received")
        
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Empty payload'}), 400
        
        # Store webhook data
        webhook_data = WebhookData(
            event_type='users',
            payload=payload,
            headers=dict(request.headers),
            processed=True
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        logger.info(f"Users webhook processed and stored: {webhook_data.id}")
        
        return jsonify({'message': 'Users webhook processed'}), 200
        
    except Exception as e:
        logger.error(f"Error processing users webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/messaging', methods=['POST'])
def handle_unipile_messaging():
    """Handle Unipile messaging-related webhooks."""
    try:
        logger.info("Unipile messaging webhook received")
        
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Empty payload'}), 400
        
        # Store webhook data
        webhook_data = WebhookData(
            event_type='messaging',
            payload=payload,
            headers=dict(request.headers),
            processed=True
        )
        
        db.session.add(webhook_data)
        db.session.commit()
        
        logger.info(f"Messaging webhook processed and stored: {webhook_data.id}")
        
        return jsonify({'message': 'Messaging webhook processed'}), 200
        
    except Exception as e:
        logger.error(f"Error processing messaging webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
