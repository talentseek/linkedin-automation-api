"""
Comparative analytics across campaigns/clients.

This module contains functionality for:
- Client comparative analytics
- System-wide comparative analytics
- Performance benchmarking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, current_app
from sqlalchemy import func, and_, or_, desc, asc

from src.extensions import db
from src.models import Campaign, Lead, Event, Client

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import analytics_bp


@analytics_bp.route('/clients/<client_id>/comparative-analytics', methods=['GET'])
def client_comparative_analytics(client_id):
    """Get comparative analytics for a specific client across all their campaigns."""
    try:
        # Get client
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all campaigns for this client
        campaigns = Campaign.query.filter_by(client_id=client_id).all()
        
        campaign_analytics = []
        for campaign in campaigns:
            # Get leads for this campaign
            leads = Lead.query.filter(
                Lead.campaign_id == campaign.id,
                Lead.created_at >= start_date
            ).all()
            
            # Calculate metrics
            total_leads = len(leads)
            connected_leads = len([l for l in leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
            responded_leads = len([l for l in leads if l.status in ['responded', 'completed']])
            
            # Calculate rates
            connection_rate = (connected_leads / total_leads * 100) if total_leads > 0 else 0
            response_rate = (responded_leads / total_leads * 100) if total_leads > 0 else 0
            
            campaign_analytics.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'campaign_status': campaign.status,
                'metrics': {
                    'total_leads': total_leads,
                    'connected_leads': connected_leads,
                    'responded_leads': responded_leads,
                    'connection_rate': round(connection_rate, 2),
                    'response_rate': round(response_rate, 2)
                }
            })
        
        # Calculate client-wide metrics
        all_leads = Lead.query.join(Campaign).filter(
            Campaign.client_id == client_id,
            Lead.created_at >= start_date
        ).all()
        
        total_client_leads = len(all_leads)
        total_client_connected = len([l for l in all_leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
        total_client_responded = len([l for l in all_leads if l.status in ['responded', 'completed']])
        
        client_connection_rate = (total_client_connected / total_client_leads * 100) if total_client_leads > 0 else 0
        client_response_rate = (total_client_responded / total_client_leads * 100) if total_client_leads > 0 else 0
        
        return jsonify({
            'client_id': client_id,
            'client_name': client.name,
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'client_summary': {
                'total_campaigns': len(campaigns),
                'total_leads': total_client_leads,
                'total_connected': total_client_connected,
                'total_responded': total_client_responded,
                'overall_connection_rate': round(client_connection_rate, 2),
                'overall_response_rate': round(client_response_rate, 2)
            },
            'campaign_analytics': campaign_analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting client comparative analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/comparative/campaigns', methods=['GET'])
def system_comparative_analytics():
    """Get comparative analytics across all campaigns in the system."""
    try:
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all campaigns
        campaigns = Campaign.query.all()
        
        campaign_analytics = []
        for campaign in campaigns:
            # Get leads for this campaign
            leads = Lead.query.filter(
                Lead.campaign_id == campaign.id,
                Lead.created_at >= start_date
            ).all()
            
            # Calculate metrics
            total_leads = len(leads)
            connected_leads = len([l for l in leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
            responded_leads = len([l for l in leads if l.status in ['responded', 'completed']])
            
            # Calculate rates
            connection_rate = (connected_leads / total_leads * 100) if total_leads > 0 else 0
            response_rate = (responded_leads / total_leads * 100) if total_leads > 0 else 0
            
            campaign_analytics.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'client_id': campaign.client_id,
                'campaign_status': campaign.status,
                'metrics': {
                    'total_leads': total_leads,
                    'connected_leads': connected_leads,
                    'responded_leads': responded_leads,
                    'connection_rate': round(connection_rate, 2),
                    'response_rate': round(response_rate, 2)
                }
            })
        
        # Sort by response rate (best performing first)
        campaign_analytics.sort(key=lambda x: x['metrics']['response_rate'], reverse=True)
        
        # Limit results
        campaign_analytics = campaign_analytics[:limit]
        
        # Calculate system-wide metrics
        all_leads = Lead.query.filter(Lead.created_at >= start_date).all()
        
        total_system_leads = len(all_leads)
        total_system_connected = len([l for l in all_leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
        total_system_responded = len([l for l in all_leads if l.status in ['responded', 'completed']])
        
        system_connection_rate = (total_system_connected / total_system_leads * 100) if total_system_leads > 0 else 0
        system_response_rate = (total_system_responded / total_system_leads * 100) if total_system_leads > 0 else 0
        
        return jsonify({
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'system_summary': {
                'total_campaigns': len(campaigns),
                'total_leads': total_system_leads,
                'total_connected': total_system_connected,
                'total_responded': total_system_responded,
                'overall_connection_rate': round(system_connection_rate, 2),
                'overall_response_rate': round(system_response_rate, 2)
            },
            'top_performing_campaigns': campaign_analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting system comparative analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500
