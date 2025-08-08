from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Campaign, Client
from sqlalchemy.exc import IntegrityError
import uuid

campaign_bp = Blueprint('campaign', __name__)


@campaign_bp.route('/clients/<client_id>/campaigns', methods=['POST'])
@jwt_required()
def create_campaign(client_id):
    """Create a new campaign for a client."""
    try:
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'Campaign name is required'}), 400
        
        campaign = Campaign(
            client_id=client_id,
            name=data['name'],
            timezone=data.get('timezone', 'UTC'),
            sequence_json=data.get('sequence_json'),
            status=data.get('status', 'draft')
        )
        
        db.session.add(campaign)
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign created successfully',
            'campaign': campaign.to_dict()
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Campaign creation failed'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@campaign_bp.route('/clients/<client_id>/campaigns', methods=['GET'])
@jwt_required()
def get_campaigns(client_id):
    """Get all campaigns for a client."""
    try:
        # Verify client exists
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        campaigns = Campaign.query.filter_by(client_id=client_id).all()
        return jsonify({
            'campaigns': [campaign.to_dict() for campaign in campaigns]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@campaign_bp.route('/campaigns/<campaign_id>', methods=['GET'])
@jwt_required()
def get_campaign(campaign_id):
    """Get a specific campaign by ID."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        return jsonify({
            'campaign': campaign.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@campaign_bp.route('/campaigns/<campaign_id>', methods=['PUT'])
@jwt_required()
def update_campaign(campaign_id):
    """Update a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            campaign.name = data['name']
        if 'timezone' in data:
            campaign.timezone = data['timezone']
        if 'sequence_json' in data:
            campaign.sequence_json = data['sequence_json']
        if 'status' in data:
            campaign.status = data['status']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign updated successfully',
            'campaign': campaign.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@campaign_bp.route('/campaigns/<campaign_id>', methods=['DELETE'])
@jwt_required()
def delete_campaign(campaign_id):
    """Delete a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        db.session.delete(campaign)
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@campaign_bp.route('/campaigns/<campaign_id>/leads', methods=['GET'])
@jwt_required()
def get_campaign_leads(campaign_id):
    """Get all leads for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        leads = campaign.leads
        return jsonify({
            'leads': [lead.to_dict() for lead in leads],
            'total_count': len(leads)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

