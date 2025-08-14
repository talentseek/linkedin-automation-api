from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Client
from sqlalchemy.exc import IntegrityError
import uuid

client_bp = Blueprint('client', __name__)


@client_bp.route('/clients', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def create_client():
    """Create a new client."""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'Client name is required'}), 400
        
        client = Client(name=data['name'])
        db.session.add(client)
        db.session.commit()
        
        return jsonify({
            'message': 'Client created successfully',
            'client': client.to_dict()
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Client creation failed'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@client_bp.route('/clients', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_clients():
    """Get all clients."""
    try:
        clients = Client.query.all()
        return jsonify({
            'clients': [client.to_dict() for client in clients]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@client_bp.route('/clients/<client_id>', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_client(client_id):
    """Get a specific client by ID."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        return jsonify({
            'client': client.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@client_bp.route('/clients/<client_id>', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
def update_client(client_id):
    """Update a client."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            client.name = data['name']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Client updated successfully',
            'client': client.to_dict()
        }), 200
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Client update failed'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


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

