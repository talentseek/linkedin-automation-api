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
        
        # Call the relation processing function with timeout protection
        try:
            logger.info("About to call _check_single_account_relations")
            logger.info(f"Function is callable: {callable(_check_single_account_relations)}")
            
            # Add a simple timeout mechanism
            import signal
            import threading
            
            def timeout_handler():
                logger.error("Relation processing timed out after 30 seconds")
                return
            
            # Call the function with a timeout
            result = None
            error = None
            
            def process_relations():
                nonlocal result, error
                try:
                    result = _check_single_account_relations(account_id, unipile)
                except Exception as e:
                    error = e
            
            thread = threading.Thread(target=process_relations)
            thread.daemon = True
            thread.start()
            thread.join(timeout=30)  # 30 second timeout
            
            if thread.is_alive():
                logger.error("Relation processing timed out")
                return jsonify({'error': 'Relation processing timed out after 30 seconds'}), 500
            
            if error:
                logger.error(f"Error in _check_single_account_relations: {str(error)}")
                return jsonify({'error': f'Relation processing failed: {str(error)}'}), 500
            
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


@webhook_bp.route('/test-single-relation', methods=['POST'])
def test_single_relation():
    """Test processing a single relation to isolate the hanging issue."""
    try:
        data = request.get_json()
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400

        account_id = data['account_id']
        logger.info(f"Testing single relation processing for account: {account_id}")

        # Get one relation from Unipile
        unipile = UnipileClient()
        relations = unipile.get_relations(account_id=account_id)
        
        if not relations or 'items' not in relations or not relations['items']:
            return jsonify({'error': 'No relations found'}), 404
        
        # Take the first relation
        relation = relations['items'][0]
        logger.info(f"Testing with relation: {relation.get('public_identifier', 'unknown')}")
        
        # Import the function
        from src.services.scheduler.connection_checker import _process_relation
        
        # Process the single relation
        try:
            logger.info("About to process single relation")
            _process_relation(relation, account_id)
            logger.info("Single relation processing completed successfully")
            
            return jsonify({
                'message': 'Single relation processed successfully',
                'relation': {
                    'public_identifier': relation.get('public_identifier'),
                    'member_id': relation.get('member_id'),
                    'name': f"{relation.get('first_name', '')} {relation.get('last_name', '')}".strip()
                }
            }), 200
            
        except Exception as e:
            logger.error(f"Error processing single relation: {str(e)}")
            return jsonify({'error': f'Single relation processing failed: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in test_single_relation: {str(e)}")
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
                # Try different response structures
                relations_items = None
                if 'relations' in relations_response and 'items' in relations_response['relations']:
                    relations_items = relations_response['relations']['items']
                elif 'items' in relations_response:
                    relations_items = relations_response['items']
                else:
                    relations_items = []
                
                results['relations_found'] = len(relations_items) if relations_items else 0
                results['steps'].append({
                    'step': 'get_relations',
                    'status': 'success',
                    'relations_count': len(relations_items) if relations_items else 0,
                    'response_keys': list(relations_response.keys()),
                    'full_response': relations_response,  # Add full response for debugging
                    'parsed_items_count': len(relations_items) if relations_items else 0
                })
            else:
                results['steps'].append({
                    'step': 'get_relations',
                    'status': 'error',
                    'error': 'Invalid response format',
                    'response_type': type(relations_response).__name__,
                    'full_response': relations_response  # Add full response for debugging
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
                'account_id': account.account_id,
                'client_id': account.client_id,
                'status': account.status,
                'connected_at': account.connected_at.isoformat() if account.connected_at else None
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


@webhook_bp.route('/test-all-unipile-endpoints', methods=['POST'])
def test_all_unipile_endpoints():
    """Test all Unipile API endpoints to identify which ones are working and which need fixing."""
    try:
        data = request.get_json()
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400
        
        account_id = data['account_id']
        logger.info(f"Testing all Unipile endpoints for account: {account_id}")
        
        unipile = UnipileClient()
        results = {}
        
        # Test 1: Get account details
        try:
            account_details = unipile.get_account(account_id)
            results['get_account'] = {
                'status': 'success',
                'data': {
                    'account_name': account_details.get('name'),
                    'account_status': account_details.get('status'),
                    'account_type': account_details.get('type')
                }
            }
        except Exception as e:
            results['get_account'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 2: Get relations
        try:
            relations = unipile.get_relations(account_id=account_id)
            results['get_relations'] = {
                'status': 'success',
                'data': {
                    'relations_count': len(relations.get('items', [])),
                    'has_cursor': 'cursor' in relations
                }
            }
        except Exception as e:
            results['get_relations'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 3: Get sent invitations (this endpoint might not exist)
        try:
            invitations = unipile.get_sent_invitations(account_id)
            results['get_sent_invitations'] = {
                'status': 'success',
                'data': {
                    'invitations_count': len(invitations.get('items', []))
                }
            }
        except Exception as e:
            results['get_sent_invitations'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 4: Get conversations
        try:
            conversations = unipile.get_conversations(account_id)
            results['get_conversations'] = {
                'status': 'success',
                'data': {
                    'conversations_count': len(conversations.get('items', []))
                }
            }
        except Exception as e:
            results['get_conversations'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 5: Get messages
        try:
            messages = unipile.get_messages(account_id, limit=10)
            results['get_messages'] = {
                'status': 'success',
                'data': {
                    'messages_count': len(messages.get('items', []))
                }
            }
        except Exception as e:
            results['get_messages'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 6: Get user profile (test with a known profile)
        try:
            # Test with a sample profile ID
            test_profile_id = "chandan-jha-29882a222"
            profile = unipile.get_user_profile(test_profile_id, account_id)
            results['get_user_profile'] = {
                'status': 'success',
                'data': {
                    'profile_name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                }
            }
        except Exception as e:
            results['get_user_profile'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 7: Get search parameters
        try:
            search_params = unipile.get_search_parameters(account_id, param_type='LOCATION', limit=5)
            results['get_search_parameters'] = {
                'status': 'success',
                'data': {
                    'parameters_count': len(search_params.get('items', []))
                }
            }
        except Exception as e:
            results['get_search_parameters'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 8: List webhooks
        try:
            webhooks = unipile.list_webhooks()
            results['list_webhooks'] = {
                'status': 'success',
                'data': {
                    'webhooks_count': len(webhooks.get('items', []))
                }
            }
        except Exception as e:
            results['list_webhooks'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 9: Get first level connections (used in lead management)
        try:
            connections = unipile.get_first_level_connections(account_id=account_id)
            results['get_first_level_connections'] = {
                'status': 'success',
                'data': {
                    'connections_count': len(connections.get('items', []))
                }
            }
        except Exception as e:
            results['get_first_level_connections'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 10: Get LinkedIn profile (used in lead management)
        try:
            # Test with a sample profile ID
            test_profile_id = "chandan-jha-29882a222"
            profile_data = unipile.get_linkedin_profile(account_id, test_profile_id)
            results['get_linkedin_profile'] = {
                'status': 'success',
                'data': {
                    'profile_name': f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}".strip()
                }
            }
        except Exception as e:
            results['get_linkedin_profile'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 11: Send connection request (critical for outreach)
        try:
            # Test with a sample profile ID - this will fail but we can see the error
            test_profile_id = "test-profile-id"
            result = unipile.send_connection_request(account_id, test_profile_id, "Test connection request")
            results['send_connection_request'] = {
                'status': 'success',
                'data': {
                    'request_id': result.get('id', 'unknown')
                }
            }
        except Exception as e:
            results['send_connection_request'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 12: Send message (critical for messaging)
        try:
            # Test with sample data - this will fail but we can see the error
            test_conversation_id = "test-conversation-id"
            result = unipile.send_message(account_id, test_conversation_id, "Test message")
            results['send_message'] = {
                'status': 'success',
                'data': {
                    'message_id': result.get('id', 'unknown')
                }
            }
        except Exception as e:
            results['send_message'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test 13: Create webhook (used in webhook management)
        try:
            # Test webhook creation - this will create a test webhook
            test_webhook_url = "https://example.com/test-webhook"
            webhook = unipile.create_webhook(test_webhook_url, "users", "Test Webhook")
            results['create_webhook'] = {
                'status': 'success',
                'data': {
                    'webhook_id': webhook.get('id', 'unknown'),
                    'webhook_name': webhook.get('name', 'unknown')
                }
            }
            # Clean up the test webhook
            if webhook.get('id'):
                try:
                    unipile.delete_webhook(webhook['id'])
                except:
                    pass  # Ignore cleanup errors
        except Exception as e:
            results['create_webhook'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Summary
        working_endpoints = [k for k, v in results.items() if v['status'] == 'success']
        broken_endpoints = [k for k, v in results.items() if v['status'] == 'error']
        
        return jsonify({
            'account_id': account_id,
            'summary': {
                'total_endpoints_tested': len(results),
                'working_endpoints': len(working_endpoints),
                'broken_endpoints': len(broken_endpoints),
                'working_endpoints_list': working_endpoints,
                'broken_endpoints_list': broken_endpoints
            },
            'detailed_results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing Unipile endpoints: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Import the handler functions for testing
from .handlers import handle_new_relation_webhook, handle_message_received_webhook


@webhook_bp.route('/campaigns/<campaign_id>/error-analysis', methods=['GET'])
def analyze_campaign_errors(campaign_id):
    """Analyze error patterns for a specific campaign."""
    try:
        from src.models import Lead, Event
        from sqlalchemy import func
        
        # Get all leads with error status
        error_leads = Lead.query.filter_by(
            campaign_id=campaign_id,
            status='error'
        ).all()
        
        error_analysis = {
            'campaign_id': campaign_id,
            'total_error_leads': len(error_leads),
            'error_breakdown': {},
            'recent_errors': [],
            'common_patterns': {}
        }
        
        # Analyze each error lead
        for lead in error_leads:
            # Get recent events for this lead
            recent_events = Event.query.filter_by(lead_id=lead.id)\
                .order_by(Event.timestamp.desc())\
                .limit(5)\
                .all()
            
            lead_error_info = {
                'lead_id': lead.id,
                'name': f"{lead.first_name} {lead.last_name}",
                'company': lead.company_name,
                'public_identifier': lead.public_identifier,
                'current_step': lead.current_step,
                'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None,
                'recent_events': []
            }
            
            for event in recent_events:
                event_info = {
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(),
                    'meta': event.meta_json
                }
                lead_error_info['recent_events'].append(event_info)
                
                # Track error patterns
                if event.event_type in ['connection_request_failed', 'message_failed']:
                    error_type = event.event_type
                    if error_type not in error_analysis['error_breakdown']:
                        error_analysis['error_breakdown'][error_type] = 0
                    error_analysis['error_breakdown'][error_type] += 1
                    
                    # Extract error message from meta
                    if event.meta_json and 'error' in event.meta_json:
                        error_msg = event.meta_json['error']
                        if 'Unable to resolve LinkedIn provider ID' in error_msg:
                            if 'provider_id_resolution' not in error_analysis['common_patterns']:
                                error_analysis['common_patterns']['provider_id_resolution'] = 0
                            error_analysis['common_patterns']['provider_id_resolution'] += 1
                        elif '422' in error_msg or 'duplicate' in error_msg.lower():
                            if 'duplicate_invitation' not in error_analysis['common_patterns']:
                                error_analysis['common_patterns']['duplicate_invitation'] = 0
                            error_analysis['common_patterns']['duplicate_invitation'] += 1
                        elif 'rate limit' in error_msg.lower():
                            if 'rate_limit' not in error_analysis['common_patterns']:
                                error_analysis['common_patterns']['rate_limit'] = 0
                            error_analysis['common_patterns']['rate_limit'] += 1
                        else:
                            if 'other_errors' not in error_analysis['common_patterns']:
                                error_analysis['common_patterns']['other_errors'] = []
                            error_analysis['common_patterns']['other_errors'].append(error_msg[:100])
            
            error_analysis['recent_errors'].append(lead_error_info)
        
        return jsonify(error_analysis), 200
        
    except Exception as e:
        logger.error(f"Error analyzing campaign errors: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/campaigns/<campaign_id>/reset-error-leads', methods=['POST'])
def reset_error_leads(campaign_id):
    """Reset error status for leads that were stuck due to historical API issues."""
    try:
        from src.models import Lead, Event
        from datetime import datetime, timedelta
        
        # Get all leads with error status
        error_leads = Lead.query.filter_by(
            campaign_id=campaign_id,
            status='error'
        ).all()
        
        reset_count = 0
        reset_details = []
        
        for lead in error_leads:
            # Check if this is a historical error (older than 1 day)
            recent_error_events = Event.query.filter_by(
                lead_id=lead.id,
                event_type='connection_request_failed'
            ).order_by(Event.timestamp.desc()).limit(1).all()
            
            should_reset = False
            error_reason = "Unknown"
            
            if recent_error_events:
                latest_error = recent_error_events[0]
                # Check if error is older than 1 day
                if latest_error.timestamp < datetime.utcnow() - timedelta(days=1):
                    should_reset = True
                    error_reason = "Historical API issue"
                    
                    # Check for specific error patterns
                    if latest_error.meta_json and 'error' in latest_error.meta_json:
                        error_msg = latest_error.meta_json['error']
                        if 'unexpected keyword argument' in error_msg:
                            error_reason = "Historical method signature issue"
            
            if should_reset:
                # Reset to appropriate status based on current step
                if lead.current_step == 0:
                    lead.status = 'pending_invite'
                elif lead.current_step > 0:
                    lead.status = 'connected'  # Assume they got past the connection step
                
                # Create reset event
                reset_event = Event(
                    event_type='lead_status_reset',
                    lead_id=lead.id,
                    meta_json={
                        'reason': error_reason,
                        'old_status': 'error',
                        'new_status': lead.status,
                        'reset_timestamp': datetime.utcnow().isoformat()
                    }
                )
                
                db.session.add(reset_event)
                reset_count += 1
                
                reset_details.append({
                    'lead_id': lead.id,
                    'name': f"{lead.first_name} {lead.last_name}",
                    'company': lead.company_name,
                    'old_status': 'error',
                    'new_status': lead.status,
                    'current_step': lead.current_step,
                    'reason': error_reason
                })
        
        if reset_count > 0:
            db.session.commit()
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_error_leads': len(error_leads),
            'reset_count': reset_count,
            'reset_details': reset_details,
            'message': f'Reset {reset_count} leads from error status'
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting error leads: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/fix-users-webhook', methods=['POST'])
def fix_users_webhook():
    """Fix the users webhook to point to the correct endpoint for new_relation events."""
    try:
        from src.services.unipile_client import UnipileClient
        
        # Create Unipile client
        unipile = UnipileClient()
        
        # Delete any existing webhooks pointing to example.com
        existing_webhooks = unipile.list_webhooks()
        for webhook in existing_webhooks.get('webhooks', {}).get('items', []):
            if webhook.get('request_url') == 'https://example.com/test-webhook':
                logger.info(f"Deleting misconfigured webhook: {webhook.get('id')}")
                unipile.delete_webhook(webhook.get('id'))
        
        # Create new webhook for users source with new_relation events
        webhook_url = "https://linkedin-automation-api.fly.dev/api/v1/webhooks/unipile/simple"
        webhook = unipile.create_webhook(
            request_url=webhook_url,
            webhook_type="users",
            name="LinkedIn Connection Monitor",
            events=["new_relation"]
        )
        
        return jsonify({
            'message': 'Users webhook fixed successfully',
            'webhook': webhook,
            'webhook_url': webhook_url,
            'events': ["new_relation"]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fixing users webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/fix-connection-status', methods=['POST'])
def fix_connection_status():
    """Fix leads that have connection_accepted events but are still in error status."""
    try:
        from src.models import Lead, Event
        from datetime import datetime
        
        # Find leads that have connection_accepted events but are in error status
        error_leads = Lead.query.filter_by(status='error').all()
        
        fixed_leads = []
        
        for lead in error_leads:
            # Check if this lead has a connection_accepted event
            connection_event = Event.query.filter_by(
                lead_id=lead.id,
                event_type='connection_accepted'
            ).first()
            
            if connection_event:
                # Update lead status to connected
                old_status = lead.status
                lead.status = 'connected'
                lead.connected_at = datetime.utcnow()
                
                # Create a fix event
                fix_event = Event(
                    event_type='lead_status_fixed',
                    lead_id=lead.id,
                    meta_json={
                        'reason': 'Manual fix for connection detection issue',
                        'old_status': old_status,
                        'new_status': 'connected',
                        'connection_event_id': connection_event.id,
                        'fix_timestamp': datetime.utcnow().isoformat()
                    }
                )
                
                db.session.add(fix_event)
                fixed_leads.append({
                    'lead_id': lead.id,
                    'name': f"{lead.first_name} {lead.last_name}",
                    'company': lead.company_name,
                    'old_status': old_status,
                    'new_status': 'connected',
                    'connection_event_timestamp': connection_event.timestamp.isoformat()
                })
        
        if fixed_leads:
            db.session.commit()
        
        return jsonify({
            'message': f'Fixed {len(fixed_leads)} leads with connection_accepted events',
            'fixed_leads': fixed_leads
        }), 200
        
    except Exception as e:
        logger.error(f"Error fixing connection status: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/reset-leads-for-messaging', methods=['POST'])
def reset_leads_for_messaging():
    """Reset specific leads from error status to connected status so they can receive messages."""
    try:
        from src.models import Lead, Event
        from datetime import datetime
        
        # Get the specific leads that need to be reset
        lead_names = [
            ("Asad", "Khan"),
            ("Henry", "Allen"), 
            ("Thi", "Luu")
        ]
        
        reset_leads = []
        
        for first_name, last_name in lead_names:
            lead = Lead.query.filter_by(
                campaign_id="b86d3871-7eb9-449d-9c4f-154ae1c4262e",
                first_name=first_name,
                last_name=last_name
            ).first()
            
            if lead and lead.status == 'error':
                # Reset to connected status
                old_status = lead.status
                lead.status = 'connected'
                lead.connected_at = datetime.utcnow()
                
                # Create a reset event
                reset_event = Event(
                    event_type='lead_status_reset_for_messaging',
                    lead_id=lead.id,
                    meta_json={
                        'reason': 'Reset from error to connected to enable messaging',
                        'old_status': old_status,
                        'new_status': 'connected',
                        'current_step': lead.current_step,
                        'reset_timestamp': datetime.utcnow().isoformat()
                    }
                )
                
                db.session.add(reset_event)
                reset_leads.append({
                    'lead_id': lead.id,
                    'name': f"{lead.first_name} {lead.last_name}",
                    'company': lead.company_name,
                    'old_status': old_status,
                    'new_status': 'connected',
                    'current_step': lead.current_step,
                    'next_message_step': lead.current_step
                })
        
        if reset_leads:
            db.session.commit()
        
        return jsonify({
            'message': f'Reset {len(reset_leads)} leads from error to connected status',
            'reset_leads': reset_leads
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting leads for messaging: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
