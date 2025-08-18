"""
Basic CRUD operations for leads.

This module contains the core CRUD endpoints:
- Create lead
- List leads
- Get lead details
- Update lead
- Delete lead
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from src.models import db, Lead, Campaign
from src.routes.lead import lead_bp
from src.utils.error_handling import (
    handle_validation_error,
    handle_database_error,
    handle_not_found_error,
    validate_required_fields,
    handle_exception
)
import logging

logger = logging.getLogger(__name__)


@lead_bp.route('/campaigns/<campaign_id>/leads', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def create_lead(campaign_id):
    """Create a new lead for a campaign."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found_error("Campaign", campaign_id)
        
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_required_fields(data, ['public_identifier'])
        if validation_error:
            return validation_error
        
        lead = Lead(
            campaign_id=campaign_id,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            company_name=data.get('company_name'),
            public_identifier=data['public_identifier'],
            provider_id=data.get('provider_id'),
            status=data.get('status', 'pending_invite')
        )
        
        db.session.add(lead)
        db.session.commit()
        
        return jsonify({
            'message': 'Lead created successfully',
            'lead': lead.to_dict()
        }), 201
        
    except IntegrityError as e:
        db.session.rollback()
        return handle_database_error(e, "lead creation")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating lead: {str(e)}")
        return handle_exception(e, "lead creation")


@lead_bp.route('/campaigns/<campaign_id>/leads', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def list_leads(campaign_id):
    """List leads for a campaign (diagnostics: includes public_identifier/provider_id/status)."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found_error("Campaign", campaign_id)
        
        # Get query parameters for filtering and pagination
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        status = request.args.get('status')
        
        # Build query
        query = Lead.query.filter_by(campaign_id=campaign_id)
        
        # Apply status filter if provided
        if status:
            query = query.filter_by(status=status)
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        leads = query.all()
        
        def to_minimal_dict(lead: Lead):
            return {
                'id': lead.id,
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'company_name': lead.company_name,
                'public_identifier': lead.public_identifier,
                'provider_id': lead.provider_id,
                'status': lead.status,
                'conversation_id': lead.conversation_id,
                'current_step': lead.current_step,
                'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None,
            }
        
        return jsonify({
            'campaign_id': campaign_id,
            'total': len(leads),
            'limit': limit,
            'offset': offset,
            'leads': [to_minimal_dict(l) for l in leads]
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing leads: {str(e)}")
        return handle_exception(e, "lead listing")


@lead_bp.route('/leads/<lead_id>', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_lead(lead_id):
    """Get lead details by ID."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        return jsonify(lead.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
def update_lead(lead_id):
    """Update lead details."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'company_name', 'status', 'current_step']
        for field in allowed_fields:
            if field in data:
                setattr(lead, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lead updated successfully',
            'lead': lead.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>', methods=['DELETE'])
# @jwt_required()  # Temporarily removed for development
def delete_lead(lead_id):
    """Delete a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        db.session.delete(lead)
        db.session.commit()
        
        return jsonify({'message': 'Lead deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting lead: {str(e)}")
        return jsonify({'error': str(e)}), 500
