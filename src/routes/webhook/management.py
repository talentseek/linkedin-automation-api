"""
Webhook management operations.

This module contains endpoints for:
- Webhook listing and management
- Webhook registration
- Webhook deletion
- Webhook configuration
"""

import logging
from flask import request, jsonify
from src.models import db
from src.services.unipile_client import UnipileClient
from src.routes.webhook import webhook_bp
from datetime import datetime

logger = logging.getLogger(__name__)


@webhook_bp.route('/list', methods=['GET'])
def list_webhooks():
    """List all webhooks configured in Unipile."""
    try:
        # Use Unipile API to list webhooks
        unipile = UnipileClient()
        webhooks = unipile.list_webhooks()

        # Normalize shape and compute total count
        total = 0
        if isinstance(webhooks, dict):
            items = webhooks.get('webhooks', {}).get('items') if isinstance(webhooks.get('webhooks'), dict) else webhooks.get('items')
            if isinstance(items, list):
                total = len(items)
        else:
            try:
                total = len(webhooks)
            except Exception:
                total = 0

        return jsonify({
            'webhooks': webhooks,
            'total': total
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing webhooks: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/register', methods=['POST'])
def register_webhook():
    """Register a new webhook with Unipile."""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'Webhook URL is required'}), 400
        
        url = data['url']
        events = data.get('events', ['new_relation', 'message_received', 'message_read'])
        
        # Use Unipile API to register webhook
        unipile = UnipileClient()
        webhook = unipile.create_webhook(
            request_url=url, 
            webhook_type="messaging",
            name="LinkedIn Webhook",
            events=events
        )
        
        return jsonify({
            'message': 'Webhook registered successfully',
            'webhook': webhook
        }), 201
        
    except Exception as e:
        logger.error(f"Error registering webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/delete/<webhook_id>', methods=['DELETE'])
def delete_webhook(webhook_id):
    """Delete a webhook from Unipile."""
    try:
        # Use Unipile API to delete webhook
        unipile = UnipileClient()
        result = unipile.delete_webhook(webhook_id=webhook_id)
        
        return jsonify({
            'message': 'Webhook deleted successfully',
            'webhook_id': webhook_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/configure-unified', methods=['POST'])
def configure_unified_webhook():
    """Configure the unified webhook endpoint."""
    try:
        data = request.get_json()
        
        if not data or 'webhook_url' not in data:
            return jsonify({'error': 'Webhook URL is required'}), 400
        
        webhook_url = data['webhook_url']
        
        # Configure the unified webhook
        unipile = UnipileClient()
        
        # Delete existing webhooks
        existing_webhooks = unipile.list_webhooks()
        for webhook in existing_webhooks.get('webhooks', {}).get('items', []):
            if webhook.get('request_url') == webhook_url:
                unipile.delete_webhook(webhook.get('id'))
        
        # Register new unified webhook for messaging events
        messaging_events = ['message_received', 'message_read', 'message_reaction', 'message_edited', 'message_deleted']
        webhook = unipile.create_webhook(
            request_url=webhook_url, 
            webhook_type="messaging",
            name="LinkedIn Messaging Monitor",
            events=messaging_events
        )
        
        return jsonify({
            'message': 'Unified webhook configured successfully',
            'webhook': webhook,
            'events': messaging_events
        }), 200
        
    except Exception as e:
        logger.error(f"Error configuring unified webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500
