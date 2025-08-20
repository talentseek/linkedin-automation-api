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
            
            # Call the function and capture any return value
            result = _check_single_account_relations(account_id, unipile)
            logger.info(f"Function returned: {result}")
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


@webhook_bp.route('/test-relation-processing', methods=['POST'])
def test_relation_processing():
    """Test relation processing directly and return detailed results."""
    try:
        data = request.get_json()
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400

        account_id = data['account_id']
        results = {
            'account_id': account_id,
            'timestamp': datetime.utcnow().isoformat(),
            'steps': [],
            'relations_found': 0,
            'leads_processed': 0,
            'leads_updated': 0,
            'errors': []
        }

        # Step 1: Test function existence
        try:
            results['steps'].append({
                'step': 'function_check',
                'status': 'success',
                'function_exists': _check_single_account_relations is not None,
                'function_type': type(_check_single_account_relations).__name__
            })
        except Exception as e:
            results['steps'].append({
                'step': 'function_check',
                'status': 'error',
                'error': str(e)
            })
            results['errors'].append(f"Function check failed: {str(e)}")

        # Step 2: Test Unipile client
        try:
            unipile = UnipileClient()
            results['steps'].append({
                'step': 'unipile_client',
                'status': 'success',
                'client_created': True
            })
        except Exception as e:
            results['steps'].append({
                'step': 'unipile_client',
                'status': 'error',
                'error': str(e)
            })
            results['errors'].append(f"Unipile client failed: {str(e)}")
            return jsonify(results), 500

        # Step 2.5: Get account details to verify account_id
        try:
            account_details = unipile.get_account(account_id)
            results['steps'].append({
                'step': 'get_account_details',
                'status': 'success',
                'account_type': account_details.get('type'),
                'account_status': account_details.get('status'),
                'account_name': account_details.get('name')
            })
        except Exception as e:
            results['steps'].append({
                'step': 'get_account_details',
                'status': 'error',
                'error': str(e)
            })
            results['errors'].append(f"Get account details failed: {str(e)}")
            return jsonify(results), 500

        # Note: Account status is null, but according to Unipile docs, we can still retrieve data
        # even when status is not OK (though it may not be up-to-date)

        # Step 3: Get relations
        try:
            relations_response = unipile.get_relations(account_id=account_id)
            if relations_response and isinstance(relations_response, dict):
                relations_items = relations_response.get('relations', {}).get('items', [])
                results['relations_found'] = len(relations_items)
                results['steps'].append({
                    'step': 'get_relations',
                    'status': 'success',
                    'relations_count': len(relations_items),
                    'response_keys': list(relations_response.keys())
                })
            else:
                results['steps'].append({
                    'step': 'get_relations',
                    'status': 'error',
                    'error': 'Invalid response format',
                    'response_type': type(relations_response).__name__
                })
                results['errors'].append("Invalid relations response format")
                return jsonify(results), 500
        except Exception as e:
            results['steps'].append({
                'step': 'get_relations',
                'status': 'error',
                'error': str(e)
            })
            results['errors'].append(f"Get relations failed: {str(e)}")
            return jsonify(results), 500

        # Step 4: Process each relation manually
        if results['relations_found'] > 0:
            relations_items = relations_response.get('relations', {}).get('items', [])
            for i, relation in enumerate(relations_items[:5]):  # Limit to first 5 for testing
                try:
                    user_provider_id = relation.get('user_provider_id')
                    user_public_identifier = relation.get('user_public_identifier')
                    user_full_name = relation.get('user_full_name')
                    
                    # Find lead by public_identifier
                    lead = None
                    if user_public_identifier:
                        lead = Lead.query.filter_by(public_identifier=user_public_identifier).first()
                    
                    relation_result = {
                        'relation_index': i,
                        'public_identifier': user_public_identifier,
                        'provider_id': user_provider_id,
                        'full_name': user_full_name,
                        'lead_found': lead is not None,
                        'lead_id': lead.id if lead else None,
                        'lead_status': lead.status if lead else None
                    }
                    
                    if lead and lead.status in ['invite_sent', 'invited']:
                        relation_result['would_update'] = True
                        relation_result['old_status'] = lead.status
                        relation_result['new_status'] = 'connected'
                    else:
                        relation_result['would_update'] = False
                    
                    results['steps'].append({
                        'step': f'process_relation_{i}',
                        'status': 'success',
                        'result': relation_result
                    })
                    
                    results['leads_processed'] += 1
                    if relation_result.get('would_update'):
                        results['leads_updated'] += 1
                        
                except Exception as e:
                    results['steps'].append({
                        'step': f'process_relation_{i}',
                        'status': 'error',
                        'error': str(e)
                    })
                    results['errors'].append(f"Relation {i} processing failed: {str(e)}")

        return jsonify(results), 200

    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


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


@webhook_bp.route('/find-linkedin-accounts', methods=['GET'])
def find_linkedin_accounts():
    """Find all LinkedIn accounts in the database."""
    try:
        from src.models.linkedin_account import LinkedInAccount
        
        accounts = LinkedInAccount.query.all()
        results = []
        
        for account in accounts:
            results.append({
                'id': account.id,
                'name': account.name,
                'account_id': account.account_id,
                'provider_id': account.provider_id,
                'created_at': account.created_at.isoformat() if account.created_at else None
            })
        
        return jsonify({
            'linkedin_accounts': results,
            'count': len(results),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


# Import the handler functions for testing
from .handlers import handle_new_relation_webhook, handle_message_received_webhook
