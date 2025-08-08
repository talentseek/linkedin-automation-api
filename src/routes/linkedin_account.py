from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, LinkedInAccount, Client
from sqlalchemy.exc import IntegrityError
import uuid

linkedin_account_bp = Blueprint('linkedin_account', __name__)


@linkedin_account_bp.route('/clients/<client_id>/linkedin-accounts', methods=['POST'])
@jwt_required()
def create_linkedin_account(client_id):
    """Create a new LinkedIn account for a client."""
    try:
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'Account ID is required'}), 400
        
        linkedin_account = LinkedInAccount(
            client_id=client_id,
            account_id=data['account_id'],
            status=data.get('status', 'pending')
        )
        
        db.session.add(linkedin_account)
        db.session.commit()
        
        return jsonify({
            'message': 'LinkedIn account created successfully',
            'linkedin_account': linkedin_account.to_dict()
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'LinkedIn account with this ID already exists'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@linkedin_account_bp.route('/clients/<client_id>/linkedin-accounts', methods=['GET'])
@jwt_required()
def get_linkedin_accounts(client_id):
    """Get all LinkedIn accounts for a client."""
    try:
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        linkedin_accounts = LinkedInAccount.query.filter_by(client_id=client_id).all()
        return jsonify({
            'linkedin_accounts': [account.to_dict() for account in linkedin_accounts]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@linkedin_account_bp.route('/linkedin-accounts/<account_id>', methods=['GET'])
@jwt_required()
def get_linkedin_account(account_id):
    """Get a specific LinkedIn account by ID."""
    try:
        linkedin_account = LinkedInAccount.query.get(account_id)
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        return jsonify({
            'linkedin_account': linkedin_account.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@linkedin_account_bp.route('/linkedin-accounts/<account_id>', methods=['PUT'])
@jwt_required()
def update_linkedin_account(account_id):
    """Update a LinkedIn account."""
    try:
        linkedin_account = LinkedInAccount.query.get(account_id)
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'status' in data:
            linkedin_account.status = data['status']
        
        if 'connected_at' in data:
            from datetime import datetime
            linkedin_account.connected_at = datetime.fromisoformat(data['connected_at'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'LinkedIn account updated successfully',
            'linkedin_account': linkedin_account.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@linkedin_account_bp.route('/linkedin-accounts/<account_id>', methods=['DELETE'])
@jwt_required()
def delete_linkedin_account(account_id):
    """Delete a LinkedIn account."""
    try:
        linkedin_account = LinkedInAccount.query.get(account_id)
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        db.session.delete(linkedin_account)
        db.session.commit()
        
        return jsonify({
            'message': 'LinkedIn account deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

