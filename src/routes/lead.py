from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from src.models import db, Lead, Campaign, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient, UnipileAPIError
from src.services.search_parameters_helper import SearchParametersHelper, build_sales_director_search, build_tech_engineer_search, build_cxo_search
from datetime import datetime
import logging
import uuid
import sys

lead_bp = Blueprint('lead', __name__)
logger = logging.getLogger(__name__)


@lead_bp.route('/campaigns/<campaign_id>/leads', methods=['POST'])
@jwt_required()
def create_lead(campaign_id):
    """Create a new lead for a campaign."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'public_identifier' not in data:
            return jsonify({'error': 'Public identifier is required'}), 400
        
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
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Lead creation failed'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads', methods=['GET'])
@jwt_required()
def list_leads(campaign_id):
    """List leads for a campaign (diagnostics: includes public_identifier/provider_id/status)."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
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
        return jsonify({'campaign_id': campaign_id, 'total': len(leads), 'leads': [to_minimal_dict(l) for l in leads]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/import', methods=['POST'])
@jwt_required()
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
        # Unipile API returns 'items' not 'profiles'
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
                
                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=profile.get('first_name'),
                    last_name=profile.get('last_name'),
                    company_name=profile.get('company_name'),
                    public_identifier=public_identifier,
                    status='pending_invite'
                )
                
                db.session.add(lead)
                imported_leads.append(lead.to_dict())
                
            except Exception as e:
                errors.append(f"Error processing profile {profile.get('public_identifier', 'unknown')}: {str(e)}")
                logger.error(f"Error processing profile: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads',
            'imported_leads': imported_leads,
            'total_imported': len(imported_leads),
            'errors': errors
        }), 200
        
    except UnipileAPIError as e:
        db.session.rollback()
        logger.error(f"Unipile API error: {str(e)}")
        return jsonify({'error': f'LinkedIn search failed: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing leads: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/import-from-url', methods=['POST'])
@jwt_required()
def import_leads_from_sales_navigator_url(campaign_id):
    """Import leads from a LinkedIn Sales Navigator URL."""
    try:
        import urllib.parse
        import re
        
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'sales_navigator_url' not in data:
            return jsonify({'error': 'Sales Navigator URL is required'}), 400
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=data['account_id'],
            client_id=campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Flags/controls
        treat_as_first_level = bool(data.get('treat_as_first_level', False))
        dry_run = bool(data.get('dry_run', False))
        raw_title_filter = data.get('title_filter') or data.get('title_filters') or []
        if isinstance(raw_title_filter, str):
            title_filter = [raw_title_filter]
        elif isinstance(raw_title_filter, list):
            title_filter = [str(t) for t in raw_title_filter]
        else:
            title_filter = []

        # Parse the Sales Navigator URL
        url = data['sales_navigator_url']
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Extract search parameters from the URL
        search_params = {}
        
        # Parse the query parameter which contains the search filters
        if 'query' in query_params:
            query_string = query_params['query'][0]
            
            # Extract filters from the query string
            # This is a simplified parser - you might need to enhance it based on the actual URL structure
            
            # Look for specific filter patterns
            if 'COMPANY_HEADCOUNT' in query_string:
                search_params['company_size'] = '51-200'  # Based on your URL
            
            if 'Chief%2520Financial%2520Officer' in query_string:
                search_params['title'] = 'Chief Financial Officer'
            
            if '2nd%2520degree%2520connections' in query_string:
                search_params['connection_degree'] = '2nd'
            
            if 'Posted%2520on%2520LinkedIn' in query_string:
                search_params['has_posted'] = True
        
        # Add any additional search parameters from the request
        if 'additional_params' in data:
            search_params.update(data['additional_params'])
        
        logger.info(f"Using Sales Navigator URL: {url}")
        
        # Use Unipile API to search for profiles using the URL directly
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_from_url(
            account_id=linkedin_account.account_id,
            url=url
        )
        
        imported_leads = []
        errors = []
        duplicates_skipped = []
        duplicates_across_campaigns = []
        
        # Process each profile from search results
        # Unipile API returns 'items' not 'profiles'
        profiles = search_results.get('items', [])

        # Apply optional title/headline filtering (case-insensitive)
        def _profile_matches_title_filters(p, filters):
            if not filters:
                return True
            try:
                haystack_parts = []
                for key in ('headline', 'title'):
                    val = p.get(key)
                    if isinstance(val, str):
                        haystack_parts.append(val)
                # current_positions may be a list of dicts with 'title'
                for pos in (p.get('current_positions') or []):
                    t = pos.get('title') or pos.get('role') or ''
                    if isinstance(t, str):
                        haystack_parts.append(t)
                haystack = ' \n '.join(haystack_parts).lower()
                return any(str(f).lower() in haystack for f in filters)
            except Exception:
                return False

        filtered_profiles = [pr for pr in profiles if _profile_matches_title_filters(pr, title_filter)]

        if dry_run:
            # Return preview without persisting
            return jsonify({
                'success': True,
                'message': 'Dry run preview from Sales Navigator URL',
                'url_used': url,
                'requested_flags': {
                    'treat_as_first_level': treat_as_first_level,
                    'dry_run': dry_run,
                    'title_filter': title_filter,
                },
                'summary': {
                    'total_profiles_found': len(profiles),
                    'total_after_title_filter': len(filtered_profiles),
                },
                'preview_profiles': [
                    {
                        'public_identifier': p.get('public_identifier'),
                        'first_name': p.get('first_name'),
                        'last_name': p.get('last_name'),
                        'headline': p.get('headline'),
                        'provider_id': p.get('id') or p.get('provider_id')
                    }
                    for p in filtered_profiles[:20]
                ]
            }), 200
        
        for profile in filtered_profiles:
            try:
                # Extract profile information
                public_identifier = profile.get('public_identifier')
                if not public_identifier:
                    continue
                
                # Check if lead already exists in this campaign
                existing_lead = Lead.find_duplicates_in_campaign(public_identifier, campaign_id)
                
                if existing_lead:
                    duplicates_skipped.append({
                        'public_identifier': public_identifier,
                        'name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                        'existing_lead_id': existing_lead.id,
                        'existing_status': existing_lead.status
                    })
                    continue  # Skip if already exists
                
                # Check for duplicates across campaigns for the same client
                cross_campaign_duplicates = Lead.find_duplicates_across_campaigns(
                    public_identifier, 
                    client_id=campaign.client_id
                )
                
                if cross_campaign_duplicates:
                    duplicates_across_campaigns.append({
                        'public_identifier': public_identifier,
                        'name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                        'existing_campaigns': [
                            {
                                'campaign_id': dup.campaign_id,
                                'campaign_name': dup.campaign.name,
                                'lead_status': dup.status
                            } for dup in cross_campaign_duplicates
                        ]
                    })
                
                # Determine status and sequencing based on flags
                status = 'connected' if treat_as_first_level else 'pending_invite'
                current_step = 1 if treat_as_first_level else 0

                # Provider id resolution
                provider_id = profile.get('id') or profile.get('provider_id')
                if treat_as_first_level and not provider_id:
                    try:
                        prof = unipile.get_user_profile(
                            identifier=public_identifier,
                            account_id=linkedin_account.account_id
                        )
                        provider_id = prof.get('provider_id') or prof.get('member_id')
                    except Exception:
                        provider_id = None

                # Company name fallback: prefer explicit field, else headline
                company_name = profile.get('company_name')
                if not company_name:
                    company_name = profile.get('headline') or None

                # Create new lead
                lead = Lead(
                    campaign_id=campaign_id,
                    first_name=profile.get('first_name'),
                    last_name=profile.get('last_name'),
                    company_name=company_name,
                    public_identifier=public_identifier,
                    provider_id=provider_id,
                    status=status,
                    current_step=current_step,
                    meta_json={'source': 'first_level_connections'} if treat_as_first_level else None
                )
                
                db.session.add(lead)
                imported_leads.append(lead.to_dict())
                
            except Exception as e:
                errors.append(f"Error processing profile {profile.get('public_identifier', 'unknown')}: {str(e)}")
                logger.error(f"Error processing profile: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads from Sales Navigator URL',
            'imported_leads': imported_leads,
            'total_imported': len(imported_leads),
            'duplicates_skipped': duplicates_skipped,
            'duplicates_across_campaigns': duplicates_across_campaigns,
            'summary': {
                'total_profiles_found': len(profiles),
                'total_after_title_filter': len(filtered_profiles),
                'new_leads_imported': len(imported_leads),
                'duplicates_in_campaign': len(duplicates_skipped),
                'duplicates_across_campaigns': len(duplicates_across_campaigns),
                'errors': len(errors)
            },
            'url_used': url,
            'requested_flags': {
                'treat_as_first_level': treat_as_first_level,
                'dry_run': dry_run,
                'title_filter': title_filter,
            },
            'errors': errors
        }), 200
        
    except UnipileAPIError as e:
        db.session.rollback()
        logger.error(f"Unipile API error: {str(e)}")
        return jsonify({'error': f'LinkedIn search failed: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing leads from URL: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/check-duplicates', methods=['POST'])
@jwt_required()
def check_duplicates_before_import(campaign_id):
    """Check for potential duplicates before importing leads."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'public_identifiers' not in data:
            return jsonify({'error': 'List of public identifiers is required'}), 400
        
        public_identifiers = data['public_identifiers']
        
        duplicates_in_campaign = []
        duplicates_across_campaigns = []
        new_profiles = []
        
        for public_identifier in public_identifiers:
            # Check for duplicates in current campaign
            existing_in_campaign = Lead.find_duplicates_in_campaign(public_identifier, campaign_id)
            if existing_in_campaign:
                duplicates_in_campaign.append({
                    'public_identifier': public_identifier,
                    'existing_lead_id': existing_in_campaign.id,
                    'existing_status': existing_in_campaign.status
                })
                continue
            
            # Check for duplicates across campaigns for the same client
            cross_campaign_duplicates = Lead.find_duplicates_across_campaigns(
                public_identifier, 
                client_id=campaign.client_id
            )
            
            if cross_campaign_duplicates:
                duplicates_across_campaigns.append({
                    'public_identifier': public_identifier,
                    'existing_campaigns': [
                        {
                            'campaign_id': dup.campaign_id,
                            'campaign_name': dup.campaign.name,
                            'lead_status': dup.status
                        } for dup in cross_campaign_duplicates
                    ]
                })
            else:
                new_profiles.append(public_identifier)
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_checked': len(public_identifiers),
            'new_profiles': new_profiles,
            'duplicates_in_campaign': duplicates_in_campaign,
            'duplicates_across_campaigns': duplicates_across_campaigns,
            'summary': {
                'new_profiles_count': len(new_profiles),
                'duplicates_in_campaign_count': len(duplicates_in_campaign),
                'duplicates_across_campaigns_count': len(duplicates_across_campaigns)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking duplicates: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/search', methods=['POST'])
@jwt_required()
def search_linkedin_profiles(campaign_id):
    """Search LinkedIn profiles using advanced search parameters."""
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
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Get search configuration from request
        search_config = data.get('search_config', {})
        
        if not search_config:
            return jsonify({'error': 'Search configuration is required'}), 400
        
        # Pagination parameters
        max_pages = data.get('max_pages', 1)  # Default to 1 page for search preview
        page_limit = data.get('page_limit', 10)  # Results per page (Unipile default)
        start = data.get('start', 0)  # Starting position
        
        # Add pagination parameters to search config
        if 'limit' not in search_config:
            search_config['limit'] = page_limit
        if 'start' not in search_config:
            search_config['start'] = start
        
        # Use Unipile API to perform advanced search
        unipile = UnipileClient()
        search_results = unipile.search_linkedin_advanced(
            account_id=linkedin_account.account_id,
            search_config=search_config
        )
        
        # Get pagination info
        paging = search_results.get('paging', {})
        total_count = paging.get('total_count', 0)
        current_page_count = paging.get('page_count', 0)
        
        return jsonify({
            'campaign_id': campaign_id,
            'message': 'Search completed successfully',
            'search_results': search_results,
            'total_results': total_count,
            'current_page': {
                'start': start,
                'limit': page_limit,
                'count': current_page_count
            },
            'pagination_info': {
                'total_count': total_count,
                'current_page_count': current_page_count,
                'has_more': (start + page_limit) < total_count,
                'next_start': start + page_limit if (start + page_limit) < total_count else None
            }
        }), 200
        
    except UnipileAPIError as e:
        logger.error(f"Unipile API error during search: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/search-and-import', methods=['POST'])
@jwt_required()
def search_and_import_leads(campaign_id):
    """Search LinkedIn profiles and import them as leads with duplication management."""
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
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Get search configuration from request
        search_config = data.get('search_config', {})
        
        if not search_config:
            return jsonify({'error': 'Search configuration is required'}), 400
        
        # Pagination parameters
        max_pages = data.get('max_pages', 5)  # Default to 5 pages (50 leads)
        max_leads = data.get('max_leads', 100)  # Default to 100 leads max
        page_limit = data.get('page_limit', 10)  # Results per page (Unipile default)
        
        # Add limit to search config if not present
        if 'limit' not in search_config:
            search_config['limit'] = page_limit
        
        # Use Unipile API to perform advanced search with pagination
        unipile = UnipileClient()
        
        imported_leads = []
        duplicates_skipped = []
        duplicates_across_campaigns = []
        errors = []
        total_profiles_found = 0
        pages_processed = 0
        
        # Start with first page (no cursor)
        cursor = None
        
        while pages_processed < max_pages and len(imported_leads) < max_leads:
            # Add pagination parameters to search config
            current_search_config = search_config.copy()
            current_search_config['limit'] = page_limit
            
            # Add cursor if we have one
            if cursor:
                current_search_config['cursor'] = cursor
            
            logger.info(f"Processing page {pages_processed + 1}, cursor: {cursor}, limit: {page_limit}")
            
            search_results = unipile.search_linkedin_advanced(
                account_id=linkedin_account.account_id,
                search_config=current_search_config
            )
            
            # Process each profile from search results
            profiles = search_results.get('items', [])
            total_profiles_found += len(profiles)
            
            if not profiles:
                logger.info(f"No more profiles found at page {pages_processed + 1}")
                break
            
            for profile in profiles:
                # Stop if we've reached max_leads
                if len(imported_leads) >= max_leads:
                    break
                    
                try:
                    # Extract profile information
                    if profile.get('type') != 'PEOPLE':
                        continue
                    
                    public_identifier = profile.get('public_identifier')
                    if not public_identifier:
                        continue
                    
                    # Check for duplicates in current campaign
                    existing_lead = Lead.find_duplicates_in_campaign(public_identifier, campaign_id)
                    if existing_lead:
                        duplicates_skipped.append({
                            'public_identifier': public_identifier,
                            'name': profile.get('name', 'Unknown'),
                            'existing_lead_id': existing_lead.id,
                            'existing_status': existing_lead.status
                        })
                        continue
                    
                    # Check for duplicates across campaigns
                    cross_campaign_duplicates = Lead.find_duplicates_across_campaigns(
                        public_identifier, campaign.client_id
                    )
                    
                    if cross_campaign_duplicates:
                        duplicates_across_campaigns.append({
                            'public_identifier': public_identifier,
                            'name': profile.get('name', 'Unknown'),
                            'existing_campaigns': [
                                {
                                    'campaign_id': dup.campaign_id,
                                    'campaign_name': dup.campaign.name if dup.campaign else 'Unknown',
                                    'lead_status': dup.status
                                }
                                for dup in cross_campaign_duplicates
                            ]
                        })
                    
                    # Create new lead
                    lead = Lead(
                        campaign_id=campaign_id,
                        first_name=profile.get('first_name'),
                        last_name=profile.get('last_name'),
                        company_name=profile.get('current_positions', [{}])[0].get('company') if profile.get('current_positions') else None,
                        public_identifier=public_identifier,
                        provider_id=profile.get('id'),
                        status='pending_invite'
                    )
                    
                    db.session.add(lead)
                    imported_leads.append(lead.to_dict())
                    
                except Exception as e:
                    logger.error(f"Error processing profile: {str(e)}")
                    errors.append({
                        'profile': profile.get('public_identifier', 'Unknown'),
                        'error': str(e)
                    })
            
            # Get cursor for next page
            paging = search_results.get('paging', {})
            cursor = paging.get('cursor')
            pages_processed += 1
            
            # Check if we've reached the end of results (no more cursor)
            if not cursor:
                logger.info("Reached end of search results (no more cursor)")
                break
        
        # Commit all leads
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads from advanced search across {pages_processed} pages',
            'imported_leads': imported_leads,
            'total_imported': len(imported_leads),
            'duplicates_skipped': duplicates_skipped,
            'duplicates_across_campaigns': duplicates_across_campaigns,
            'summary': {
                'total_profiles_found': total_profiles_found,
                'new_leads_imported': len(imported_leads),
                'duplicates_in_campaign': len(duplicates_skipped),
                'duplicates_across_campaigns': len(duplicates_across_campaigns),
                'errors': len(errors),
                'pages_processed': pages_processed,
                'max_pages_requested': max_pages,
                'max_leads_requested': max_leads
            },
            'search_config_used': search_config,
            'pagination_info': {
                'max_pages': max_pages,
                'max_leads': max_leads,
                'page_limit': page_limit,
                'pages_processed': pages_processed
            },
            'errors': errors
        }), 200
        
    except UnipileAPIError as e:
        logger.error(f"Unipile API error during search and import: {str(e)}")
        return jsonify({'error': f'Search and import failed: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during search and import: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/smart-search', methods=['POST'])
@jwt_required()
def smart_search_and_import_leads(campaign_id):
    """
    Smart search and import using predefined patterns or custom parameters.
    This makes it easy to build complex searches like "sales directors in tech companies in Sweden".
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
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Get search type and parameters
        search_type = data.get('search_type', 'custom')  # 'custom', 'sales_director', 'tech_engineer', 'cxo'
        search_params = data.get('search_params', {})
        
        # Build search configuration based on type
        helper = SearchParametersHelper()
        
        if search_type == 'sales_director':
            search_config = build_sales_director_search(
                location_name=search_params.get('location', 'sweden'),
                company_size_min=search_params.get('company_size_min', 51),
                company_size_max=search_params.get('company_size_max', 1000),
                industry_name=search_params.get('industry', 'technology')
            )
        elif search_type == 'tech_engineer':
            search_config = build_tech_engineer_search(
                location_name=search_params.get('location', 'sweden'),
                company_size_min=search_params.get('company_size_min', 51),
                company_size_max=search_params.get('company_size_max', 1000),
                seniority_level=search_params.get('seniority', 'senior')
            )
        elif search_type == 'cxo':
            search_config = build_cxo_search(
                location_name=search_params.get('location', 'sweden'),
                company_size_min=search_params.get('company_size_min', 51),
                company_size_max=search_params.get('company_size_max', 1000)
            )
        elif search_type == 'custom':
            # Use the helper to build custom search
            search_config = helper.build_search(**search_params)
        else:
            return jsonify({'error': f'Unknown search type: {search_type}'}), 400
        
        # Pagination parameters
        max_pages = data.get('max_pages', 5)
        max_leads = data.get('max_leads', 100)
        page_limit = data.get('page_limit', 10)
        
        # Add limit to search config
        search_config['limit'] = page_limit
        
        # Use Unipile API to perform search with pagination
        unipile = UnipileClient()
        
        imported_leads = []
        duplicates_skipped = []
        duplicates_across_campaigns = []
        errors = []
        total_profiles_found = 0
        pages_processed = 0
        
        # Start with first page (no cursor)
        cursor = None
        
        while pages_processed < max_pages and len(imported_leads) < max_leads:
            # Add pagination parameters to search config
            current_search_config = search_config.copy()
            current_search_config['limit'] = page_limit
            
            # Add cursor if we have one
            if cursor:
                current_search_config['cursor'] = cursor
            
            logger.info(f"Processing page {pages_processed + 1}, cursor: {cursor}, limit: {page_limit}")
            
            search_results = unipile.search_linkedin_advanced(
                account_id=linkedin_account.account_id,
                search_config=current_search_config
            )
            
            # Process each profile from search results
            profiles = search_results.get('items', [])
            total_profiles_found += len(profiles)
            
            if not profiles:
                logger.info(f"No more profiles found at page {pages_processed + 1}")
                break
            
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
                        duplicates_skipped.append({
                            'public_identifier': public_identifier,
                            'name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                            'existing_lead_id': existing_lead.id,
                            'existing_status': existing_lead.status
                        })
                        continue
                    
                    # Check for duplicates across campaigns
                    cross_campaign_duplicates = Lead.query.filter_by(
                        public_identifier=public_identifier
                    ).filter(
                        Lead.campaign_id != campaign_id
                    ).all()
                    
                    if cross_campaign_duplicates:
                        duplicate_campaigns = []
                        for dup_lead in cross_campaign_duplicates:
                            dup_campaign = Campaign.query.get(dup_lead.campaign_id)
                            if dup_campaign:
                                duplicate_campaigns.append({
                                    'campaign_id': dup_lead.campaign_id,
                                    'campaign_name': dup_campaign.name,
                                    'lead_status': dup_lead.status
                                })
                        
                        duplicates_across_campaigns.append({
                            'public_identifier': public_identifier,
                            'name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                            'existing_campaigns': duplicate_campaigns
                        })
                    
                    # Create new lead
                    lead = Lead(
                        id=str(uuid.uuid4()),
                        campaign_id=campaign_id,
                        first_name=profile.get('first_name'),
                        last_name=profile.get('last_name'),
                        company_name=profile.get('company_name'),
                        public_identifier=public_identifier,
                        provider_id=profile.get('id'),
                        status='pending_invite',
                        created_at=datetime.utcnow()
                    )
                    
                    db.session.add(lead)
                    imported_leads.append(lead.to_dict())
                    
                    # Create event for lead import
                    event = Event(
                        id=str(uuid.uuid4()),
                        lead_id=lead.id,
                        event_type='lead_imported',
                        timestamp=datetime.utcnow(),
                        meta_json={
                            'campaign_id': campaign_id,
                            'source': 'smart_search',
                            'search_type': search_type,
                            'search_config': search_config,
                            'linkedin_account_id': linkedin_account.account_id
                        }
                    )
                    db.session.add(event)
                    
                except Exception as e:
                    errors.append(f"Error processing profile {profile.get('public_identifier', 'unknown')}: {str(e)}")
                    logger.error(f"Error processing profile: {str(e)}")
            
            # Get cursor for next page
            cursor = search_results.get('paging', {}).get('cursor')
            pages_processed += 1
            
            if not cursor:
                logger.info("No more pages available")
                break
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_leads)} leads from smart search across {pages_processed} pages',
            'imported_leads': imported_leads,
            'total_imported': len(imported_leads),
            'duplicates_skipped': duplicates_skipped,
            'duplicates_across_campaigns': duplicates_across_campaigns,
            'summary': {
                'total_profiles_found': total_profiles_found,
                'new_leads_imported': len(imported_leads),
                'duplicates_in_campaign': len(duplicates_skipped),
                'duplicates_across_campaigns': len(duplicates_across_campaigns),
                'errors': len(errors),
                'pages_processed': pages_processed,
                'max_pages_requested': max_pages,
                'max_leads_requested': max_leads
            },
            'pagination_info': {
                'max_pages': max_pages,
                'max_leads': max_leads,
                'page_limit': page_limit,
                'pages_processed': pages_processed
            },
            'search_config_used': search_config,
            'search_type': search_type,
            'errors': errors
        }), 200
        
    except UnipileAPIError as e:
        db.session.rollback()
        logger.error(f"Unipile API error during smart search: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during smart search: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/smart-search-preview', methods=['POST'])
@jwt_required()
def smart_search_preview(campaign_id):
    """
    Smart search preview using predefined patterns or custom parameters.
    This shows search results without importing, so you can see the total count first.
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
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Get search type and parameters
        search_type = data.get('search_type')
        search_params = data.get('search_params', {})
        
        # Build search configuration using SearchParametersHelper
        helper = SearchParametersHelper()
        
        if search_type == 'sales_director':
            search_config = build_sales_director_search(
                location_name=search_params.get('location'),
                company_size_min=search_params.get('company_size_min'),
                company_size_max=search_params.get('company_size_max'),
                industry_name=search_params.get('industry')
            )
        elif search_type == 'tech_engineer':
            search_config = build_tech_engineer_search(
                location_name=search_params.get('location'),
                company_size_min=search_params.get('company_size_min'),
                company_size_max=search_params.get('company_size_max')
            )
        elif search_type == 'cxo':
            search_config = build_cxo_search(
                location_name=search_params.get('location'),
                company_size_min=search_params.get('company_size_min'),
                company_size_max=search_params.get('company_size_max')
            )
        elif search_type == 'custom':
            # Use custom search parameters
            search_config = helper.build_search(
                api=search_params.get('api', 'sales_navigator'),
                category=search_params.get('category', 'people'),
                keywords=search_params.get('keywords'),
                location_names=search_params.get('location_names'),
                location_ids=search_params.get('location_ids'),
                company_headcount_min=search_params.get('company_headcount_min'),
                company_headcount_max=search_params.get('company_headcount_max'),
                industry_names=search_params.get('industry_names'),
                industry_ids=search_params.get('industry_ids'),
                seniority_min=search_params.get('seniority_min'),
                seniority_max=search_params.get('seniority_max'),
                seniority_level=search_params.get('seniority_level'),
                relationship=search_params.get('relationship')
            )
        else:
            return jsonify({'error': f'Unknown search type: {search_type}'}), 400
        
        # Pagination parameters for preview
        page_limit = data.get('page_limit', 10)  # Results per page
        max_pages = data.get('max_pages', 1)  # Default to 1 page for preview
        
        # Add limit to search config
        search_config['limit'] = page_limit
        
        # Use Unipile API to perform search with pagination
        unipile = UnipileClient()
        
        total_profiles_found = 0
        pages_processed = 0
        all_profiles = []
        
        # Start with first page (no cursor)
        cursor = None
        
        while pages_processed < max_pages:
            # Add pagination parameters to search config
            current_search_config = search_config.copy()
            current_search_config['limit'] = page_limit
            
            # Add cursor if we have one
            if cursor:
                current_search_config['cursor'] = cursor
            
            logger.info(f"Processing page {pages_processed + 1}, cursor: {cursor}, limit: {page_limit}")
            
            search_results = unipile.search_linkedin_advanced(
                account_id=linkedin_account.account_id,
                search_config=current_search_config
            )
            
            # Process each profile from search results
            profiles = search_results.get('items', [])
            total_profiles_found += len(profiles)
            all_profiles.extend(profiles)
            
            if not profiles:
                logger.info(f"No more profiles found at page {pages_processed + 1}")
                break
            
            # Get cursor for next page
            cursor = search_results.get('paging', {}).get('cursor')
            pages_processed += 1
            
            if not cursor:
                logger.info("No more pages available")
                break
        
        # Get pagination info from the last search result
        paging = search_results.get('paging', {})
        total_count = paging.get('total_count', total_profiles_found)
        
        return jsonify({
            'campaign_id': campaign_id,
            'message': f'Smart search preview completed. Found {total_count} total results.',
            'search_type': search_type,
            'search_config_used': search_config,
            'total_results': total_count,
            'profiles_found_in_preview': total_profiles_found,
            'pages_processed': pages_processed,
            'preview_profiles': all_profiles[:10],  # Show first 10 profiles as preview
            'pagination_info': {
                'total_count': total_count,
                'profiles_found_in_preview': total_profiles_found,
                'pages_processed': pages_processed,
                'max_pages_requested': max_pages,
                'page_limit': page_limit,
                'has_more_pages': cursor is not None,
                'estimated_total_pages': (total_count // page_limit) + 1 if total_count > 0 else 0
            },
            'next_steps': {
                'import_endpoint': f'POST /api/leads/campaigns/{campaign_id}/leads/smart-search',
                'import_parameters': {
                    'account_id': data['account_id'],
                    'search_type': search_type,
                    'search_params': search_params,
                    'max_pages': 'number of pages to import',
                    'max_leads': 'maximum number of leads to import'
                }
            }
        }), 200
        
    except UnipileAPIError as e:
        logger.error(f"Unipile API error during smart search preview: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error during smart search preview: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/search-parameters', methods=['GET'])
@jwt_required()
def get_search_parameters():
    """Get available search parameters (locations, industries, skills, etc.)."""
    try:
        data = request.get_json() or {}
        
        if 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        param_type = data.get('type', 'LOCATION')
        keywords = data.get('keywords')
        limit = data.get('limit', 100)
        
        # Verify LinkedIn account exists
        linkedin_account = LinkedInAccount.query.get(data['account_id'])
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        if linkedin_account.status not in ['connected', 'active']:
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Use Unipile API to get search parameters
        unipile = UnipileClient()
        parameters = unipile.get_search_parameters(
            account_id=linkedin_account.account_id,
            param_type=param_type,
            keywords=keywords,
            limit=limit
        )
        
        return jsonify({
            'message': 'Search parameters retrieved successfully',
            'parameters': parameters,
            'param_type': param_type,
            'keywords': keywords
        }), 200
        
    except UnipileAPIError as e:
        logger.error(f"Unipile API error getting search parameters: {str(e)}")
        return jsonify({'error': f'Failed to get search parameters: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error getting search parameters: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/search-parameters/helper', methods=['GET'])
@jwt_required()
def get_search_helper_info():
    """Get information about available search parameters and helper functions."""
    helper = SearchParametersHelper()
    
    return jsonify({
        'message': 'Search helper information retrieved successfully',
        'common_locations': helper.COMMON_LOCATIONS,
        'common_industries': helper.COMMON_INDUSTRIES,
        'seniority_levels': helper.SENIORITY_LEVELS,
        'predefined_searches': {
            'sales_director': 'Search for sales directors in technology companies',
            'tech_engineer': 'Search for software engineers in tech companies', 
            'cxo': 'Search for C-level executives'
        },
        'usage_examples': {
            'smart_search': {
                'endpoint': 'POST /api/campaigns/{campaign_id}/leads/smart-search',
                'example': {
                    'account_id': 'linkedin_account_id',
                    'search_type': 'sales_director',
                    'search_params': {
                        'location': 'sweden',
                        'company_size_min': 51,
                        'company_size_max': 1000,
                        'industry': 'technology'
                    },
                    'max_pages': 5,
                    'max_leads': 100
                }
            }
        }
    }), 200


@lead_bp.route('/campaigns/<campaign_id>/leads/merge-duplicates', methods=['POST'])
@jwt_required()
def merge_duplicate_leads(campaign_id):
    """Merge duplicate leads across campaigns for the same client."""
    try:
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'merge_strategy' not in data:
            return jsonify({'error': 'Merge strategy is required'}), 400
        
        merge_strategy = data['merge_strategy']  # 'copy', 'move', or 'link'
        
        if merge_strategy not in ['copy', 'move', 'link']:
            return jsonify({'error': 'Invalid merge strategy. Use: copy, move, or link'}), 400
        
        # Get all leads for this client across campaigns
        client_campaigns = Campaign.query.filter_by(client_id=campaign.client_id).all()
        campaign_ids = [c.id for c in client_campaigns]
        
        # Find duplicates by public_identifier
        from sqlalchemy import func
        duplicate_identifiers = db.session.query(
            Lead.public_identifier,
            func.count(Lead.id).label('count')
        ).filter(
            Lead.campaign_id.in_(campaign_ids)
        ).group_by(
            Lead.public_identifier
        ).having(
            func.count(Lead.id) > 1
        ).all()
        
        merged_leads = []
        skipped_leads = []
        
        for public_identifier, count in duplicate_identifiers:
            # Get all leads with this public_identifier
            duplicate_leads = Lead.query.filter_by(
                public_identifier=public_identifier
            ).filter(
                Lead.campaign_id.in_(campaign_ids)
            ).all()
            
            # Find the lead in the target campaign
            target_lead = next((lead for lead in duplicate_leads if lead.campaign_id == campaign_id), None)
            
            if not target_lead:
                # No lead in target campaign, create one
                if merge_strategy == 'copy':
                    # Copy the first lead to target campaign
                    source_lead = duplicate_leads[0]
                    new_lead = Lead(
                        campaign_id=campaign_id,
                        first_name=source_lead.first_name,
                        last_name=source_lead.last_name,
                        company_name=source_lead.company_name,
                        public_identifier=source_lead.public_identifier,
                        provider_id=source_lead.provider_id,
                        status='pending_invite'  # Reset status for new campaign
                    )
                    db.session.add(new_lead)
                    merged_leads.append({
                        'public_identifier': public_identifier,
                        'action': 'copied',
                        'source_campaign_id': source_lead.campaign_id,
                        'target_campaign_id': campaign_id
                    })
                else:
                    skipped_leads.append({
                        'public_identifier': public_identifier,
                        'reason': 'No lead in target campaign and strategy is not copy'
                    })
            else:
                # Lead exists in target campaign, update if needed
                if merge_strategy == 'move':
                    # Move all other leads' data to target lead
                    for lead in duplicate_leads:
                        if lead.campaign_id != campaign_id:
                            # Update target lead with better data if available
                            if not target_lead.provider_id and lead.provider_id:
                                target_lead.provider_id = lead.provider_id
                            if not target_lead.first_name and lead.first_name:
                                target_lead.first_name = lead.first_name
                            if not target_lead.last_name and lead.last_name:
                                target_lead.last_name = lead.last_name
                            if not target_lead.company_name and lead.company_name:
                                target_lead.company_name = lead.company_name
                            
                            # Delete the duplicate lead
                            db.session.delete(lead)
                    
                    merged_leads.append({
                        'public_identifier': public_identifier,
                        'action': 'merged',
                        'target_campaign_id': campaign_id,
                        'duplicates_removed': len(duplicate_leads) - 1
                    })
                else:
                    skipped_leads.append({
                        'public_identifier': public_identifier,
                        'reason': 'Lead already exists in target campaign'
                    })
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully processed {len(merged_leads)} duplicate leads',
            'merged_leads': merged_leads,
            'skipped_leads': skipped_leads,
            'summary': {
                'total_duplicates_found': len(duplicate_identifiers),
                'successfully_merged': len(merged_leads),
                'skipped': len(skipped_leads)
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error merging duplicates: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>/convert-profile', methods=['POST'])
@jwt_required()
def convert_lead_profile(lead_id):
    """Convert lead's public identifier to provider ID using Unipile API."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        if lead.provider_id:
            return jsonify({
                'message': 'Lead already has provider ID',
                'lead': lead.to_dict()
            }), 200
        
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=data['account_id'],
            client_id=lead.campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status != 'connected':
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        # Use Unipile API to get user profile and provider ID
        unipile = UnipileClient()
        profile_data = unipile.get_user_profile(
            account_id=linkedin_account.account_id,
            identifier=lead.public_identifier
        )
        
        # Extract provider ID from profile data
        provider_id = profile_data.get('provider_id')
        if not provider_id:
            return jsonify({'error': 'Could not retrieve provider ID from profile'}), 400
        
        # Update lead with provider ID and additional profile information
        lead.provider_id = provider_id
        
        # Update other fields if available and not already set
        if not lead.first_name and profile_data.get('first_name'):
            lead.first_name = profile_data.get('first_name')
        if not lead.last_name and profile_data.get('last_name'):
            lead.last_name = profile_data.get('last_name')
        if not lead.company_name and profile_data.get('company_name'):
            lead.company_name = profile_data.get('company_name')
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lead profile converted successfully',
            'lead': lead.to_dict(),
            'provider_id': provider_id
        }), 200
        
    except UnipileAPIError as e:
        logger.error(f"Unipile API error: {str(e)}")
        return jsonify({'error': f'Profile conversion failed: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error converting lead profile: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>', methods=['GET'])
@jwt_required()
def get_lead(lead_id):
    """Get a specific lead by ID."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        return jsonify({
            'lead': lead.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>', methods=['PUT'])
@jwt_required()
def update_lead(lead_id):
    """Update a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update allowed fields
        if 'first_name' in data:
            lead.first_name = data['first_name']
        if 'last_name' in data:
            lead.last_name = data['last_name']
        if 'company_name' in data:
            lead.company_name = data['company_name']
        if 'status' in data:
            lead.status = data['status']
        if 'current_step' in data:
            lead.current_step = data['current_step']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lead updated successfully',
            'lead': lead.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/<lead_id>', methods=['DELETE'])
@jwt_required()
def delete_lead(lead_id):
    """Delete a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        db.session.delete(lead)
        db.session.commit()
        
        return jsonify({
            'message': 'Lead deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/first-level-connections', methods=['POST'])
@jwt_required()
def import_first_level_connections(campaign_id):
    """
    Import 1st level LinkedIn connections as leads.
    These are already connected, so no connection request is needed.
    """
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'error': 'account_id is required'}), 400
        
        # Get LinkedIn account (account_id can be either database ID or Unipile account_id)
        linkedin_account = LinkedInAccount.query.filter_by(id=account_id).first()
        if not linkedin_account:
            linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        # Get pagination parameters
        max_pages = data.get('max_pages', 1)
        page_limit = data.get('page_limit', 100)  # Higher limit for 1st level connections
        cursor = data.get('cursor')
        
        # Get 1st level connections using get_relations
        unipile = UnipileClient()
        all_connections = []
        current_cursor = cursor
        pages_processed = 0
        
        print(f"Starting import of 1st level connections for campaign {campaign_id}")
        print(f"Using LinkedIn account: {linkedin_account.account_id}")
        
        while pages_processed < max_pages:
            try:
                # Get relations (1st level connections)
                response = unipile.get_relations(
                    account_id=linkedin_account.account_id,
                    cursor=current_cursor,
                    limit=page_limit
                )
                
                if not response or 'items' not in response:
                    print(f"No more connections found after page {pages_processed + 1}")
                    break
                
                connections = response['items']
                if not connections:
                    print(f"No connections in page {pages_processed + 1}")
                    break
                
                all_connections.extend(connections)
                pages_processed += 1
                
                print(f"Page {pages_processed}: Found {len(connections)} connections")
                
                # Check for next page
                current_cursor = response.get('next_cursor')
                if not current_cursor:
                    print("No more pages available")
                    break
                    
            except Exception as e:
                print(f"Error fetching page {pages_processed + 1}: {str(e)}")
                break
        
        print(f"Total connections found: {len(all_connections)}")
        
        # Process and import connections
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        for connection in all_connections:
            try:
                # Extract connection data (data is directly in connection object, not nested under 'profile')
                public_identifier = connection.get('public_identifier')
                first_name = connection.get('first_name', '')
                last_name = connection.get('last_name', '')
                headline = connection.get('headline', '')
                # Note: get_relations doesn't return company/location, these would need to be fetched separately
                company = ''
                location = ''
                
                # Skip if no public identifier
                if not public_identifier:
                    skipped_count += 1
                    continue
                
                # Check if lead already exists
                existing_lead = Lead.query.filter_by(
                    campaign_id=campaign_id,
                    public_identifier=public_identifier
                ).first()
                
                if existing_lead:
                    skipped_count += 1
                    continue
                
                # Try to resolve provider_id for reliable messaging/replies
                provider_id = connection.get('provider_id')
                if not provider_id:
                    try:
                        unipile = UnipileClient()
                        profile = unipile.get_user_profile(
                            identifier=public_identifier,
                            account_id=linkedin_account.account_id
                        )
                        provider_id = profile.get('provider_id')
                    except Exception:
                        provider_id = None
                
                # Create new lead with 1st level connection status
                lead = Lead(
                    campaign_id=campaign_id,
                    public_identifier=public_identifier,
                    first_name=first_name,
                    last_name=last_name,
                    company_name=headline,  # Use headline as company_name since we don't have company field
                    provider_id=provider_id,
                    status='connected',  # Already connected - no invite needed
                    current_step=1,  # Start at first message step
                    meta_json={'source': 'first_level_connections'}
                )
                
                db.session.add(lead)
                
                # Flush to get the lead ID
                db.session.flush()
                
                imported_count += 1
                
                # Log event
                event = Event(
                    lead_id=lead.id,
                    event_type='lead_imported',
                    timestamp=datetime.utcnow(),
                    meta_json={
                        'campaign_id': campaign_id,
                        'source': 'first_level_connections',
                        'connection_data': connection
                    }
                )
                db.session.add(event)
                
            except Exception as e:
                print(f"Error processing connection {public_identifier}: {str(e)}")
                error_count += 1
                continue
        
        # Commit all changes
        try:
            db.session.commit()
        except Exception as e:
            print(f"Error during database commit: {str(e)}")
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {imported_count} 1st level connections',
            'summary': {
                'total_connections_found': len(all_connections),
                'imported': imported_count,
                'skipped': skipped_count,
                'errors': error_count,
                'pages_processed': pages_processed
            },
            'next_cursor': current_cursor,
            'campaign_id': campaign_id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error importing 1st level connections: {str(e)}")
        return jsonify({'error': f'Failed to import 1st level connections: {str(e)}'}), 500


@lead_bp.route('/campaigns/<campaign_id>/leads/first-level-connections/preview', methods=['POST'])
@jwt_required()
def preview_first_level_connections(campaign_id):
    """
    Preview 1st level LinkedIn connections without importing.
    """
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'error': 'account_id is required'}), 400
        
        # Get LinkedIn account (account_id can be either database ID or Unipile account_id)
        linkedin_account = LinkedInAccount.query.filter_by(id=account_id).first()
        if not linkedin_account:
            linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        # Get pagination parameters
        max_pages = data.get('max_pages', 1)
        page_limit = data.get('page_limit', 100)
        cursor = data.get('cursor')
        
        # Get 1st level connections
        unipile = UnipileClient()
        all_connections = []
        current_cursor = cursor
        pages_processed = 0
        total_estimated = 0
        
        while pages_processed < max_pages:
            try:
                response = unipile.get_relations(
                    account_id=linkedin_account.account_id,
                    cursor=current_cursor,
                    limit=page_limit
                )
                
                if not response or 'items' not in response:
                    break
                
                connections = response['items']
                if not connections:
                    break
                
                all_connections.extend(connections)
                pages_processed += 1
                
                # Check for next page
                current_cursor = response.get('next_cursor')
                if not current_cursor:
                    break
                    
            except Exception as e:
                print(f"Error fetching page {pages_processed + 1}: {str(e)}")
                break
        
        # Prepare preview data
        preview_connections = []
        for connection in all_connections[:10]:  # Show first 10
            preview_connections.append({
                'public_identifier': connection.get('public_identifier'),
                'first_name': connection.get('first_name', ''),
                'last_name': connection.get('last_name', ''),
                'headline': connection.get('headline', ''),
                'company': '',  # get_relations doesn't return company
                'location': '',  # get_relations doesn't return location
                'profile_url': connection.get('public_profile_url', f"https://www.linkedin.com/in/{connection.get('public_identifier', '')}")
            })
        
        return jsonify({
            'success': True,
            'summary': {
                'total_connections_found': len(all_connections),
                'pages_processed': pages_processed,
                'preview_count': len(preview_connections)
            },
            'preview_connections': preview_connections,
            'next_cursor': current_cursor,
            'next_steps': {
                'import_endpoint': f'/api/leads/campaigns/{campaign_id}/leads/first-level-connections',
                'method': 'POST',
                'body_example': {
                    'account_id': account_id,
                    'max_pages': 1,
                    'page_limit': 100
                }
            }
        })
        
    except Exception as e:
        print(f"Error previewing 1st level connections: {str(e)}")
        return jsonify({'error': f'Failed to preview 1st level connections: {str(e)}'}), 500

