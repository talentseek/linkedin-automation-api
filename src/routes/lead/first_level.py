"""
First level connections handling.

This module contains endpoints for:
- Importing first level connections
- Previewing first level connections
- Managing connection data
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from src.models import db, Lead, Campaign, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient, UnipileAPIError
from src.routes.lead import lead_bp
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


@lead_bp.route('/campaigns/<campaign_id>/leads/first-level-connections', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def import_first_level_connections(campaign_id):
    """Import first level connections as leads for a campaign."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=data['account_id'],
            client_id=campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status != 'connected':
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Use Unipile API to get first level connections
        unipile = UnipileClient()
        connections = unipile.get_first_level_connections(
            account_id=linkedin_account.account_id
        )
        
        imported_leads = []
        errors = []
        
        # Process each connection
        for connection in connections:
            try:
                # Extract connection information
                public_identifier = connection.get('public_identifier')
                if not public_identifier:
                    continue
                
                # Check if lead already exists in this campaign
                existing_lead = Lead.query.filter_by(
                    campaign_id=campaign_id,
                    public_identifier=public_identifier
                ).first()
                
                if existing_lead:
                    continue  # Skip if already exists
                
                # Extract company name
                company_name = None
                current_position = connection.get('current_position')
                if current_position and isinstance(current_position, dict):
                    company_name = current_position.get('company_name')
                
                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=connection.get('first_name'),
                    last_name=connection.get('last_name'),
                    company_name=company_name,
                    public_identifier=public_identifier,
                    status='connected'  # Already connected
                )
                
                db.session.add(lead)
                imported_leads.append({
                    'public_identifier': public_identifier,
                    'first_name': connection.get('first_name'),
                    'last_name': connection.get('last_name'),
                    'company_name': company_name
                })
                
            except Exception as e:
                errors.append({
                    'public_identifier': connection.get('public_identifier'),
                    'error': str(e)
                })
                logger.error(f"Error processing connection {connection.get('public_identifier')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} first level connections',
            'imported_count': len(imported_leads),
            'imported_leads': imported_leads,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing first level connections: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/first-level-connections/preview', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def preview_first_level_connections(campaign_id):
    """Preview first level connections without importing them."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=data['account_id'],
            client_id=campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status != 'connected':
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Use Unipile API to get first level connections
        unipile = UnipileClient()
        connections = unipile.get_first_level_connections(
            account_id=linkedin_account.account_id
        )
        
        # Process results
        processed_connections = []
        
        for connection in connections:
            try:
                # Extract company name
                company_name = None
                current_position = connection.get('current_position')
                if current_position and isinstance(current_position, dict):
                    company_name = current_position.get('company_name')
                
                # Check if lead already exists in this campaign
                existing_lead = Lead.query.filter_by(
                    campaign_id=campaign_id,
                    public_identifier=connection.get('public_identifier')
                ).first()
                
                processed_connections.append({
                    'public_identifier': connection.get('public_identifier'),
                    'first_name': connection.get('first_name'),
                    'last_name': connection.get('last_name'),
                    'company_name': company_name,
                    'headline': connection.get('headline'),
                    'already_imported': existing_lead is not None
                })
                
            except Exception as e:
                logger.error(f"Error processing connection {connection.get('public_identifier')}: {str(e)}")
        
        return jsonify({
            'total_connections': len(processed_connections),
            'connections': processed_connections
        }), 200
        
    except Exception as e:
        logger.error(f"Error previewing first level connections: {str(e)}")
        return jsonify({'error': str(e)}), 500
