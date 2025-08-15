"""
Lead management operations.

This module contains endpoints for:
- Lead enrichment
- Duplicate checking and merging
- Profile conversion
- Lead status management
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


@lead_bp.route('/campaigns/<campaign_id>/leads/check-duplicates', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def check_duplicates(campaign_id):
    """Check for duplicate leads in a campaign."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'leads' not in data:
            return jsonify({'error': 'Leads data is required'}), 400
        
        leads_data = data['leads']
        duplicates = []
        
        for lead_info in leads_data:
            public_identifier = lead_info.get('public_identifier')
            if not public_identifier:
                continue
            
            # Check if lead already exists
            existing_lead = Lead.query.filter_by(
                campaign_id=campaign_id,
                public_identifier=public_identifier
            ).first()
            
            if existing_lead:
                duplicates.append({
                    'public_identifier': public_identifier,
                    'existing_lead_id': existing_lead.id,
                    'existing_lead_name': f"{existing_lead.first_name} {existing_lead.last_name}",
                    'existing_lead_company': existing_lead.company_name
                })
        
        return jsonify({
            'total_checked': len(leads_data),
            'duplicates_found': len(duplicates),
            'duplicates': duplicates
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking duplicates: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/merge-duplicates', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def merge_duplicates(campaign_id):
    """Merge duplicate leads in a campaign."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'duplicates' not in data:
            return jsonify({'error': 'Duplicates data is required'}), 400
        
        duplicates_data = data['duplicates']
        merged_count = 0
        errors = []
        
        for duplicate_info in duplicates_data:
            try:
                lead_id = duplicate_info.get('lead_id')
                if not lead_id:
                    continue
                
                # Get the lead to merge
                lead = Lead.query.get(lead_id)
                if not lead or lead.campaign_id != campaign_id:
                    continue
                
                # Delete the duplicate lead
                db.session.delete(lead)
                merged_count += 1
                
            except Exception as e:
                errors.append({
                    'lead_id': duplicate_info.get('lead_id'),
                    'error': str(e)
                })
                logger.error(f"Error merging duplicate {duplicate_info.get('lead_id')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully merged {merged_count} duplicate leads',
            'merged_count': merged_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error merging duplicates: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>/convert-profile', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def convert_profile_to_lead(lead_id):
    """Convert a LinkedIn profile to a lead."""
    try:
        data = request.get_json()
        
        if not data or 'campaign_id' not in data:
            return jsonify({'error': 'Campaign ID is required'}), 400
        
        campaign_id = data['campaign_id']
        
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Verify lead exists
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Update lead campaign
        lead.campaign_id = campaign_id
        lead.status = 'pending_invite'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile converted to lead successfully',
            'lead': lead.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error converting profile to lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/enrich-company', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def enrich_company_data(campaign_id):
    """Enrich company data for leads in a campaign."""
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
        
        # Get leads that need company enrichment
        leads = Lead.query.filter_by(
            campaign_id=campaign_id,
            company_name=None
        ).all()
        
        enriched_count = 0
        errors = []
        
        # Use Unipile API to enrich company data
        unipile = UnipileClient()
        
        for lead in leads:
            try:
                if not lead.public_identifier:
                    continue
                
                # Get profile data from Unipile
                profile_data = unipile.get_linkedin_profile(
                    account_id=linkedin_account.account_id,
                    public_identifier=lead.public_identifier
                )
                
                # Extract company name from profile
                company_name = None
                if profile_data:
                    # Try to extract company from current position
                    current_position = profile_data.get('current_position')
                    if current_position and isinstance(current_position, dict):
                        company_name = current_position.get('company_name')
                    
                    # If no company in current position, try headline parsing
                    if not company_name:
                        headline = profile_data.get('headline')
                        if headline:
                            # Simple headline parsing for company
                            if ' at ' in headline.lower():
                                company_name = headline.split(' at ')[-1].split(' | ')[0].strip()
                
                if company_name:
                    lead.company_name = company_name
                    enriched_count += 1
                
            except Exception as e:
                errors.append({
                    'lead_id': lead.id,
                    'public_identifier': lead.public_identifier,
                    'error': str(e)
                })
                logger.error(f"Error enriching lead {lead.id}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully enriched {enriched_count} leads',
            'enriched_count': enriched_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error enriching company data: {str(e)}")
        return jsonify({'error': str(e)}), 500
