from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Client
from sqlalchemy.exc import IntegrityError
from src.utils.error_handling import (
    handle_validation_error,
    handle_database_error,
    handle_not_found_error,
    validate_required_fields,
    handle_exception
)
from src.services.caching import cache_response, invalidate_cache_on_change
import uuid

client_bp = Blueprint('client', __name__)


@client_bp.route('/clients', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
@invalidate_cache_on_change('client', 'client_id')
def create_client():
    """Create a new client."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_required_fields(data, ['name'])
        if validation_error:
            return validation_error
        
        client = Client(
            name=data['name'],
            email=data.get('email')  # Handle optional email field
        )
        db.session.add(client)
        db.session.commit()
        
        return jsonify({
            'message': 'Client created successfully',
            'client': client.to_dict()
        }), 201
        
    except IntegrityError as e:
        db.session.rollback()
        return handle_database_error(e, "client creation")
    except Exception as e:
        db.session.rollback()
        return handle_exception(e, "client creation")


@client_bp.route('/clients', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
@cache_response('clients:list', ttl=300)
def get_clients():
    """Get all clients with optional campaign inclusion."""
    try:
        include_campaigns = request.args.get('include_campaigns', 'false').lower() == 'true'
        
        clients = Client.query.all()
        
        if include_campaigns:
            # Import Campaign model here to avoid circular imports
            from src.models.campaign import Campaign
            
            client_data = []
            for client in clients:
                client_dict = client.to_dict()
                
                # Get campaigns for this client
                campaigns = Campaign.query.filter_by(client_id=client.id).all()
                client_dict['campaigns'] = [
                    {
                        'id': campaign.id,
                        'name': campaign.name,
                        'status': campaign.status,
                        'created_at': campaign.created_at.isoformat() if campaign.created_at else None
                    }
                    for campaign in campaigns
                ]
                
                client_data.append(client_dict)
            
            return jsonify({
                'clients': client_data
            }), 200
        else:
            # Original behavior - just return clients without campaigns
            return jsonify({
                'clients': [client.to_dict() for client in clients]
            }), 200
            
    except Exception as e:
        return handle_exception(e, "client listing")


@client_bp.route('/clients/<client_id>', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
@cache_response('clients:detail', ttl=600, key_args=['client_id'])
def get_client(client_id):
    """Get a specific client by ID."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return handle_not_found_error("Client", client_id)
        
        return jsonify({
            'client': client.to_dict()
        }), 200
    except Exception as e:
        return handle_exception(e, "client retrieval")


@client_bp.route('/clients/<client_id>', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
@invalidate_cache_on_change('client', 'client_id')
def update_client(client_id):
    """Update a client."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return handle_not_found_error("Client", client_id)
        
        data = request.get_json()
        if not data:
            return handle_validation_error("No data provided")
        
        if 'name' in data:
            client.name = data['name']
        if 'email' in data:
            client.email = data['email']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Client updated successfully',
            'client': client.to_dict()
        }), 200
        
    except IntegrityError as e:
        db.session.rollback()
        return handle_database_error(e, "client update")
    except Exception as e:
        db.session.rollback()
        return handle_exception(e, "client update")


@client_bp.route('/clients/<client_id>', methods=['DELETE'])
# @jwt_required()  # Temporarily removed for development
def delete_client(client_id):
    """Delete a client."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        db.session.delete(client)
        db.session.commit()
        
        return jsonify({
            'message': 'Client deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

