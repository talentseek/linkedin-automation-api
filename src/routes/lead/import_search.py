"""
Lead import and search functionality.

This module contains endpoints for:
- Importing leads from LinkedIn searches
- Searching for leads
- Smart search functionality
- Lead enrichment
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from src.models import db, Lead, Campaign, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient, UnipileAPIError
from src.services.search_parameters_helper import SearchParametersHelper, build_sales_director_search, build_tech_engineer_search, build_cxo_search
from src.routes.lead import lead_bp
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


def _extract_company_name_from_profile(profile: dict) -> str:
    """Best-effort company extraction from a profile dict.
    Prefers explicit fields, then current_positions, then parses headline.
    """
    try:
        if not isinstance(profile, dict):
            return None
        # 1) Explicit company fields
        for key in ('company_name', 'company', 'organization', 'org_name'):
            val = profile.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # 2) Current positions
        positions = profile.get('current_positions') or profile.get('positions') or []
        if isinstance(positions, list):
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                for key in ('company', 'company_name', 'organization', 'org_name'):
                    val = pos.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        # 3) Headline parsing patterns: " ... at Company ..." or "... @Company ..."
        headline = profile.get('headline')
        if isinstance(headline, str) and headline.strip():
            text = headline.strip()
            # Prefer substring after ' at ' or '@'
            candidate = None
            lowered = text.lower()
            if ' at ' in lowered:
                idx = lowered.find(' at ')
                candidate = text[idx + 4:]
            elif '@' in text:
                idx = text.find('@')
                candidate = text[idx + 1:]
            if candidate:
                # Stop at common separators
                for sep in [' | ', ' — ', ' – ', ' - ', ',', '  ']:
                    if sep in candidate:
                        candidate = candidate.split(sep, 1)[0]
                cleaned = candidate.strip().strip('|').strip('-').strip('—').strip('–').strip()
                # Avoid overly generic phrases
                if cleaned and len(cleaned) >= 2:
                    return cleaned
        return None
    except Exception:
        return None


@lead_bp.route('/campaigns/<campaign_id>/leads/import', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def import_leads_from_search(campaign_id):
    """Import leads from LinkedIn Sales Navigator search."""
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
        
        # Prepare search parameters
        search_params = data.get('search_params', {})
        
        # Use Unipile API to search for profiles
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_profiles(
            account_id=linkedin_account.account_id,
            search_params=search_params
        )
        
        imported_leads = []
        errors = []
        
        # Process each profile from search results
        profiles = search_results.get('items', [])
        
        for profile in profiles:
            try:
                # Extract profile information
                public_identifier = profile.get('public_identifier')
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
                company_name = _extract_company_name_from_profile(profile)
                
                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=profile.get('first_name'),
                    last_name=profile.get('last_name'),
                    company_name=company_name,
                    public_identifier=public_identifier,
                    status='pending_invite'
                )
                
                db.session.add(lead)
                imported_leads.append({
                    'public_identifier': public_identifier,
                    'first_name': profile.get('first_name'),
                    'last_name': profile.get('last_name'),
                    'company_name': company_name
                })
                
            except Exception as e:
                errors.append({
                    'public_identifier': profile.get('public_identifier'),
                    'error': str(e)
                })
                logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads',
            'imported_count': len(imported_leads),
            'imported_leads': imported_leads,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing leads: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/import-from-url', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def import_leads_from_url(campaign_id):
    """Import leads from a LinkedIn Sales Navigator URL."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
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
        
        # Use Unipile API to search for profiles from URL
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_profiles_from_url(
            account_id=linkedin_account.account_id,
            url=data['url']
        )
        
        imported_leads = []
        errors = []
        
        # Process each profile from search results
        profiles = search_results.get('items', [])
        
        for profile in profiles:
            try:
                # Extract profile information
                public_identifier = profile.get('public_identifier')
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
                company_name = _extract_company_name_from_profile(profile)
                
                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=profile.get('first_name'),
                    last_name=profile.get('last_name'),
                    company_name=company_name,
                    public_identifier=public_identifier,
                    status='pending_invite'
                )
                
                db.session.add(lead)
                imported_leads.append({
                    'public_identifier': public_identifier,
                    'first_name': profile.get('first_name'),
                    'last_name': profile.get('last_name'),
                    'company_name': company_name
                })
                
            except Exception as e:
                errors.append({
                    'public_identifier': profile.get('public_identifier'),
                    'error': str(e)
                })
                logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads',
            'imported_count': len(imported_leads),
            'imported_leads': imported_leads,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing leads from URL: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/search', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def search_leads(campaign_id):
    """Search for leads without importing them."""
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
        
        # Prepare search parameters
        search_params = data.get('search_params', {})
        
        # Use Unipile API to search for profiles
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_profiles(
            account_id=linkedin_account.account_id,
            search_params=search_params
        )
        
        # Process results
        profiles = search_results.get('items', [])
        processed_profiles = []
        
        for profile in profiles:
            try:
                # Extract company name
                company_name = _extract_company_name_from_profile(profile)
                
                # Check if lead already exists in this campaign
                existing_lead = Lead.query.filter_by(
                    campaign_id=campaign_id,
                    public_identifier=profile.get('public_identifier')
                ).first()
                
                processed_profiles.append({
                    'public_identifier': profile.get('public_identifier'),
                    'first_name': profile.get('first_name'),
                    'last_name': profile.get('last_name'),
                    'company_name': company_name,
                    'headline': profile.get('headline'),
                    'already_imported': existing_lead is not None
                })
                
            except Exception as e:
                logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
        
        return jsonify({
            'total_results': len(processed_profiles),
            'profiles': processed_profiles
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching leads: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/smart-search', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def smart_search_leads(campaign_id):
    """Smart search for leads using predefined search templates."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        if not data or 'search_type' not in data:
            return jsonify({'error': 'Search type is required'}), 400
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=data['account_id'],
            client_id=campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status != 'connected':
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Build search parameters based on type
        search_type = data['search_type']
        custom_params = data.get('custom_params', {})
        
        if search_type == 'sales_director':
            search_params = build_sales_director_search(custom_params)
        elif search_type == 'tech_engineer':
            search_params = build_tech_engineer_search(custom_params)
        elif search_type == 'cxo':
            search_params = build_cxo_search(custom_params)
        else:
            return jsonify({'error': 'Invalid search type'}), 400
        
        # Use Unipile API to search for profiles
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_profiles(
            account_id=linkedin_account.account_id,
            search_params=search_params
        )
        
        imported_leads = []
        errors = []
        
        # Process each profile from search results
        profiles = search_results.get('items', [])
        
        for profile in profiles:
            try:
                # Extract profile information
                public_identifier = profile.get('public_identifier')
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
                company_name = _extract_company_name_from_profile(profile)
                
                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=profile.get('first_name'),
                    last_name=profile.get('last_name'),
                    company_name=company_name,
                    public_identifier=public_identifier,
                    status='pending_invite'
                )
                
                db.session.add(lead)
                imported_leads.append({
                    'public_identifier': public_identifier,
                    'first_name': profile.get('first_name'),
                    'last_name': profile.get('last_name'),
                    'company_name': company_name
                })
                
            except Exception as e:
                errors.append({
                    'public_identifier': profile.get('public_identifier'),
                    'error': str(e)
                })
                logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads using {search_type} search',
            'search_type': search_type,
            'imported_count': len(imported_leads),
            'imported_leads': imported_leads,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error smart searching leads: {str(e)}")
        return jsonify({'error': str(e)}), 500
