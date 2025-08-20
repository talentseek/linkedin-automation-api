"""
Lead import and search functionality.

This module contains the single working endpoint for importing leads:
- search-and-import: Advanced search and import with proper pagination
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


@lead_bp.route('/campaigns/<campaign_id>/leads/search-and-import', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def search_and_import_leads(campaign_id):
    """Search for leads and import them with proper pagination support.
    
    This is the single, unified endpoint for all lead import scenarios:
    - URL-based imports (Sales Navigator URLs)
    - Keyword-based searches
    - Advanced search configurations
    - All with proper cursor pagination
    """
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
        
        # Get pagination parameters
        max_pages = data.get('max_pages', 25)
        max_leads = data.get('max_leads', 253)
        page_limit = data.get('page_limit', 10)
        
        # Use Unipile API to search for profiles
        unipile = UnipileClient()
        imported_leads = []
        errors = []
        total_profiles_found = 0
        pages_processed = 0
        cursor = None
        
        # Determine search type and parameters
        search_config = data.get('search_config', {})
        url = data.get('url') or search_config.get('url')
        
        if url:
            # URL-based search (Sales Navigator URL)
            while pages_processed < max_pages and len(imported_leads) < max_leads:
                try:
                    search_results = unipile.search_linkedin_from_url(
                        account_id=linkedin_account.account_id,
                        url=url,
                        cursor=cursor,
                        limit=page_limit
                    )
                    
                    profiles = search_results.get('items', [])
                    if not profiles:
                        break
                    
                    total_profiles_found += len(profiles)
                    pages_processed += 1
                    
                    for profile in profiles:
                        try:
                            public_identifier = profile.get('public_identifier')
                            if not public_identifier:
                                continue
                            
                            # Check if lead already exists
                            existing_lead = Lead.query.filter_by(
                                campaign_id=campaign_id,
                                public_identifier=public_identifier
                            ).first()
                            
                            if existing_lead:
                                continue
                            
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
                            
                            if len(imported_leads) >= max_leads:
                                break
                                
                        except Exception as e:
                            errors.append({
                                'public_identifier': profile.get('public_identifier'),
                                'error': str(e)
                            })
                            logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
                    
                    cursor = search_results.get('cursor')
                    if not cursor:
                        break
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error fetching page {pages_processed + 1}: {str(e)}")
                    errors.append({
                        'page': pages_processed + 1,
                        'error': str(e)
                    })
                    break
        else:
            # Keyword/parameter-based search
            search_params = search_config or data.get('search_params', {})
            
            while pages_processed < max_pages and len(imported_leads) < max_leads:
                try:
                    search_results = unipile.search_linkedin_profiles(
                        account_id=linkedin_account.account_id,
                        search_params=search_params,
                        cursor=cursor,
                        limit=page_limit
                    )
                    
                    profiles = search_results.get('items', [])
                    if not profiles:
                        break
                    
                    total_profiles_found += len(profiles)
                    pages_processed += 1
                    
                    for profile in profiles:
                        try:
                            public_identifier = profile.get('public_identifier')
                            if not public_identifier:
                                continue
                            
                            # Check if lead already exists
                            existing_lead = Lead.query.filter_by(
                                campaign_id=campaign_id,
                                public_identifier=public_identifier
                            ).first()
                            
                            if existing_lead:
                                continue
                            
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
                            
                            if len(imported_leads) >= max_leads:
                                break
                                
                        except Exception as e:
                            errors.append({
                                'public_identifier': profile.get('public_identifier'),
                                'error': str(e)
                            })
                            logger.error(f"Error processing profile {profile.get('public_identifier')}: {str(e)}")
                    
                    cursor = search_results.get('cursor')
                    if not cursor:
                        break
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error fetching page {pages_processed + 1}: {str(e)}")
                    errors.append({
                        'page': pages_processed + 1,
                        'error': str(e)
                    })
                    break
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads from {pages_processed} pages',
            'imported_count': len(imported_leads),
            'imported_leads': imported_leads,
            'errors': errors,
            'summary': {
                'total_profiles_found': total_profiles_found,
                'new_leads_imported': len(imported_leads),
                'pages_processed': pages_processed,
                'max_pages_requested': max_pages,
                'max_leads_requested': max_leads,
                'errors': len(errors)
            },
            'pagination_info': {
                'max_pages': max_pages,
                'max_leads': max_leads,
                'page_limit': page_limit,
                'pages_processed': pages_processed
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in search and import: {str(e)}")
        return jsonify({'error': str(e)}), 500
