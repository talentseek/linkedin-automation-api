"""
Debug and testing endpoints.

This module contains endpoints for:
- Debug webhook functionality
- Test webhook processing
- Connection checking
- Debug utilities
"""

import logging
from flask import request, jsonify
from src.models import db, Lead, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient
from src.routes.webhook import webhook_bp
from src.services.scheduler.connection_checker import _check_single_account_relations
from datetime import datetime

logger = logging.getLogger(__name__)


@webhook_bp.route('/check-connections', methods=['POST'])
def check_connections():
    """Debug endpoint to check connections for a LinkedIn account."""
    try:
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400
        
        account_id = data['account_id']
        
        # Use Unipile API to check connections
        unipile = UnipileClient()
        connections = unipile.get_first_level_connections(account_id=account_id)
        
        return jsonify({
            'account_id': account_id,
            'connections_count': len(connections),
            'connections': connections
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking connections: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-relations', methods=['POST'])
def debug_relations():
    """Debug endpoint to check relations for a LinkedIn account."""
    try:
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400
        
        account_id = data['account_id']
        
        # Use Unipile API to check relations
        unipile = UnipileClient()
        relations = unipile.get_relations(account_id=account_id)
        
        return jsonify({
            'account_id': account_id,
            'relations_count': len(relations),
            'relations': relations
        }), 200
        
    except Exception as e:
        logger.error(f"Error debugging relations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/process-relations', methods=['POST'])
def process_relations():
    """Manually process relations for a LinkedIn account and update lead statuses.

    Body: { "account_id": "<unipile_account_id>" }
    """
    try:
        data = request.get_json()
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400

        account_id = data['account_id']
        logger.info(f"Starting relation processing for account: {account_id}")

        # Test that the function exists
        try:
            logger.info(f"Function _check_single_account_relations exists: {_check_single_account_relations}")
            logger.info(f"Function type: {type(_check_single_account_relations)}")
        except Exception as e:
            logger.error(f"Error checking function existence: {str(e)}")
            return jsonify({'error': f'Function import issue: {str(e)}'}), 500

        unipile = UnipileClient()
        logger.info("UnipileClient created successfully")
        
        # Test that we can get relations first
        try:
            relations = unipile.get_relations(account_id=account_id)
            logger.info(f"Successfully got relations response: {type(relations)}")
            if relations:
                logger.info(f"Relations response keys: {list(relations.keys()) if isinstance(relations, dict) else 'not a dict'}")
        except Exception as e:
            logger.error(f"Error getting relations: {str(e)}")
            return jsonify({'error': f'Failed to get relations: {str(e)}'}), 500
        
        # Call the relation processing function
        try:
            logger.info("About to call _check_single_account_relations")
            # Add a simple test to see if the function is callable
            logger.info(f"Function is callable: {callable(_check_single_account_relations)}")
            _check_single_account_relations(account_id, unipile)
            logger.info(f"Relation processing completed for account: {account_id}")
        except Exception as e:
            logger.error(f"Error in _check_single_account_relations: {str(e)}")
            return jsonify({'error': f'Relation processing failed: {str(e)}'}), 500

        return jsonify({
            'message': 'Relation processing triggered',
            'account_id': account_id
        }), 200

    except Exception as e:
        logger.error(f"Error processing relations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-sent-invitations', methods=['POST'])
def debug_sent_invitations():
    """Debug endpoint to check sent invitations for a LinkedIn account."""
    try:
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400
        
        account_id = data['account_id']
        
        # Use Unipile API to check sent invitations
        unipile = UnipileClient()
        invitations = unipile.get_sent_invitations(account_id=account_id)
        
        return jsonify({
            'account_id': account_id,
            'invitations_count': len(invitations),
            'invitations': invitations
        }), 200
        
    except Exception as e:
        logger.error(f"Error debugging sent invitations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/test', methods=['POST'])
def test_unipile_webhook():
    """Test endpoint for Unipile webhook processing."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Test data is required'}), 400
        
        # Simulate webhook processing
        logger.info("Testing webhook processing with data:")
        logger.info(f"Test data: {data}")
        
        # Process the test data as if it were a real webhook
        event_type = data.get('type') or data.get('event')
        
        if event_type == 'new_relation':
            result = handle_new_relation_webhook(data)
        elif event_type == 'message_received':
            result = handle_message_received_webhook(data)
        else:
            result = jsonify({'message': 'Test event processed', 'event_type': event_type}), 200
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/test-connection', methods=['POST'])
def test_connection_webhook():
    """Test endpoint for connection webhook processing."""
    try:
        # Create test connection data
        test_data = {
            'type': 'new_relation',
            'account_id': 'test_account_123',
            'user_provider_id': 'test_user_456',
            'user_full_name': 'Test User',
            'user_public_identifier': 'test-user-123',
            'user_profile_url': 'https://linkedin.com/in/test-user-123'
        }
        
        logger.info("Testing connection webhook with data:")
        logger.info(f"Test data: {test_data}")
        
        # Process the test connection
        result = handle_new_relation_webhook(test_data)
        
        return jsonify({
            'message': 'Connection test completed',
            'test_data': test_data,
            'result': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing connection webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/unipile/test-message-edited', methods=['POST'])
def test_message_edited_webhook():
    """Test endpoint for message edited webhook processing."""
    try:
        # Create test message data
        test_data = {
            'type': 'message_received',
            'account_id': 'test_account_123',
            'account_info': {
                'type': 'LINKEDIN',
                'feature': 'classic'
            },
            'sender': {
                'attendee_provider_id': 'test_user_456',
                'attendee_name': 'Test User'
            },
            'message': 'This is a test message',
            'chat_id': 'test_chat_789',
            'message_id': 'test_message_101'
        }
        
        logger.info("Testing message webhook with data:")
        logger.info(f"Test data: {test_data}")
        
        # Process the test message
        result = handle_message_received_webhook(test_data)
        
        return jsonify({
            'message': 'Message test completed',
            'test_data': test_data,
            'result': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing message webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/debug-test', methods=['GET'])
def debug_test():
    """Simple debug endpoint to test if latest code is deployed."""
    try:
        # Test function import
        function_exists = _check_single_account_relations is not None
        function_type = type(_check_single_account_relations).__name__
        
        return jsonify({
            'message': 'Debug test endpoint working',
            'function_exists': function_exists,
            'function_type': function_type,
            'timestamp': datetime.utcnow().isoformat(),
            'deployment_version': 'latest'
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


# Import the handler functions for testing
from .handlers import handle_new_relation_webhook, handle_message_received_webhook
