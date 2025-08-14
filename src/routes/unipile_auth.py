from flask import Blueprint, request, jsonify, url_for, current_app
from flask_jwt_extended import jwt_required
from src.models import db, Client, LinkedInAccount, Webhook
from src.services.unipile_client import UnipileClient, UnipileAPIError
from datetime import datetime
import logging

unipile_auth_bp = Blueprint('unipile_auth', __name__)
logger = logging.getLogger(__name__)


@unipile_auth_bp.route('/clients/<client_id>/linkedin-auth', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def create_linkedin_auth_url(client_id):
    """Get existing LinkedIn accounts or create authentication URL."""
    try:
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Create Unipile client
        unipile = UnipileClient()
        
        # Get existing accounts
        try:
            accounts_response = unipile._make_request('GET', '/api/v1/accounts')
            existing_accounts = accounts_response.get('items', [])
            
            # Filter for LinkedIn accounts
            linkedin_accounts = [acc for acc in existing_accounts if acc.get('type') == 'LINKEDIN']
            
            if linkedin_accounts:
                # Return existing accounts
                return jsonify({
                    'existing_accounts': linkedin_accounts,
                    'message': 'Found existing LinkedIn accounts',
                    'client_id': client_id
                }), 200
            else:
                # No existing accounts, create auth URL
                callback_url = url_for('unipile_auth.auth_callback', client_id=client_id, _external=True)
                
                # Try alternative auth endpoint
                auth_response = unipile._make_request('POST', '/api/v1/auth/linkedin', json={
                    'redirect_uri': callback_url
                })
                
                return jsonify({
                    'auth_url': auth_response.get('auth_url'),
                    'callback_url': callback_url,
                    'client_id': client_id
                }), 200
                
        except UnipileAPIError as e:
            logger.error(f"Unipile API error: {str(e)}")
            return jsonify({'error': f'Unipile API error: {str(e)}'}), 400
            
    except Exception as e:
        logger.error(f"Error in LinkedIn auth: {str(e)}")
        return jsonify({'error': str(e)}), 500


@unipile_auth_bp.route('/auth/unipile/callback/<client_id>', methods=['GET'])
def auth_callback(client_id):
    """Handle Unipile authentication callback."""
    try:
        # Get parameters from callback
        account_id = request.args.get('account_id')
        status = request.args.get('status')
        error = request.args.get('error')
        
        if error:
            logger.error(f"Authentication error for client {client_id}: {error}")
            return jsonify({'error': f'Authentication failed: {error}'}), 400
        
        if not account_id or not status:
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Check if LinkedIn account already exists
        existing_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        
        if existing_account:
            # Update existing account
            existing_account.status = status
            if status == 'connected':
                existing_account.connected_at = datetime.utcnow()
        else:
            # Create new LinkedIn account
            linkedin_account = LinkedInAccount(
                client_id=client_id,
                account_id=account_id,
                status=status,
                connected_at=datetime.utcnow() if status == 'connected' else None
            )
            db.session.add(linkedin_account)
        
        db.session.commit()
        
        # If successfully connected, create webhooks
        if status == 'connected':
            try:
                unipile = UnipileClient()
                
                # Create webhook for user events (connection acceptance)
                webhook_url_users = url_for('unipile_auth.webhook_users', _external=True)
                users_webhook = unipile.create_webhook(
                    account_id=account_id,
                    source='users',
                    url=webhook_url_users,
                    secret=current_app.config.get('UNIPILE_WEBHOOK_SECRET')
                )
                
                # Create webhook for messaging events (replies)
                webhook_url_messaging = url_for('unipile_auth.webhook_messaging', _external=True)
                messaging_webhook = unipile.create_webhook(
                    account_id=account_id,
                    source='messaging',
                    url=webhook_url_messaging,
                    secret=current_app.config.get('UNIPILE_WEBHOOK_SECRET')
                )
                
                # Store webhook information
                users_webhook_record = Webhook(
                    account_id=existing_account.id if existing_account else linkedin_account.id,
                    source='users',
                    webhook_id=users_webhook.get('webhook_id'),
                    status='active'
                )
                
                messaging_webhook_record = Webhook(
                    account_id=existing_account.id if existing_account else linkedin_account.id,
                    source='messaging',
                    webhook_id=messaging_webhook.get('webhook_id'),
                    status='active'
                )
                
                db.session.add(users_webhook_record)
                db.session.add(messaging_webhook_record)
                db.session.commit()
                
                logger.info(f"Webhooks created for account {account_id}")
                
            except Exception as e:
                logger.error(f"Error creating webhooks: {str(e)}")
                # Don't fail the authentication if webhook creation fails
        
        return jsonify({
            'message': 'LinkedIn account connected successfully',
            'account_id': account_id,
            'status': status,
            'client_id': client_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in auth callback: {str(e)}")
        return jsonify({'error': str(e)}), 500


@unipile_auth_bp.route('/webhooks/users', methods=['POST'])
def webhook_users():
    """Handle user events webhook (connection acceptance)."""
    try:
        # Verify webhook secret
        webhook_secret = request.headers.get('X-Webhook-Secret')
        expected_secret = current_app.config.get('UNIPILE_WEBHOOK_SECRET')
        
        if webhook_secret != expected_secret:
            logger.warning("Invalid webhook secret")
            return jsonify({'error': 'Invalid webhook secret'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Process the webhook asynchronously (for now, just log it)
        logger.info(f"User webhook received: {data}")
        
        # TODO: Process connection acceptance events
        # This will be implemented in the sequence engine phase
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        logger.error(f"Error processing user webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@unipile_auth_bp.route('/webhooks/messaging', methods=['POST'])
def webhook_messaging():
    """Handle messaging events webhook (replies)."""
    try:
        # Verify webhook secret
        webhook_secret = request.headers.get('X-Webhook-Secret')
        expected_secret = current_app.config.get('UNIPILE_WEBHOOK_SECRET')
        
        if webhook_secret != expected_secret:
            logger.warning("Invalid webhook secret")
            return jsonify({'error': 'Invalid webhook secret'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Process the webhook asynchronously (for now, just log it)
        logger.info(f"Messaging webhook received: {data}")
        
        # TODO: Process reply detection events
        # This will be implemented in the sequence engine phase
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        logger.error(f"Error processing messaging webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

