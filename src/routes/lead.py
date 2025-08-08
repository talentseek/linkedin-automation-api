from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Lead, Campaign, LinkedInAccount
from src.services.unipile_client import UnipileClient, UnipileAPIError
from sqlalchemy.exc import IntegrityError
import uuid
import logging

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
        
        for profile in profiles:
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
            'message': f'Successfully imported {len(imported_leads)} leads from Sales Navigator URL',
            'imported_leads': imported_leads,
            'total_imported': len(imported_leads),
            'duplicates_skipped': duplicates_skipped,
            'duplicates_across_campaigns': duplicates_across_campaigns,
            'summary': {
                'total_profiles_found': len(profiles),
                'new_leads_imported': len(imported_leads),
                'duplicates_in_campaign': len(duplicates_skipped),
                'duplicates_across_campaigns': len(duplicates_across_campaigns),
                'errors': len(errors)
            },
            'url_used': url,
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

