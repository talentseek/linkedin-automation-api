"""
Real-time activity monitoring.

This module contains functionality for:
- Real-time activity tracking
- Recent events monitoring
- Live dashboard data
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


@analytics_bp.route('/real-time/activity', methods=['GET'])
def real_time_activity():
    """Get real-time activity across all campaigns (last 24 hours)."""
    try:
        # Get query parameters
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Get recent events
        recent_events = Event.query.filter(
            Event.timestamp >= start_time
        ).order_by(desc(Event.timestamp)).limit(limit).all()
        
        # Get event counts by type
        event_counts = db.session.query(
            Event.event_type,
            func.count(Event.id).label('count')
        ).filter(
            Event.timestamp >= start_time
        ).group_by(Event.event_type).all()
        
        # Get recent leads
        recent_leads = Lead.query.filter(
            Lead.created_at >= start_time
        ).order_by(desc(Lead.created_at)).limit(20).all()
        
        # Get active campaigns
        active_campaigns = Campaign.query.filter_by(status='active').all()
        
        # Calculate activity metrics
        total_events = sum(count for _, count in event_counts)
        total_new_leads = len(recent_leads)
        total_active_campaigns = len(active_campaigns)
        
        # Get events by campaign
        events_by_campaign = db.session.query(
            Campaign.name.label('campaign_name'),
            func.count(Event.id).label('event_count')
        ).join(Lead).join(Event).filter(
            Event.timestamp >= start_time
        ).group_by(Campaign.name).order_by(desc(func.count(Event.id))).limit(10).all()
        
        return jsonify({
            'time_range': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'hours': hours
            },
            'activity_summary': {
                'total_events': total_events,
                'total_new_leads': total_new_leads,
                'total_active_campaigns': total_active_campaigns
            },
            'event_breakdown': [
                {
                    'event_type': event_type,
                    'count': count
                }
                for event_type, count in event_counts
            ],
            'events_by_campaign': [
                {
                    'campaign_name': campaign_name,
                    'event_count': event_count
                }
                for campaign_name, event_count in events_by_campaign
            ],
            'recent_events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(),
                    'lead_id': event.lead_id,
                    'meta_json': event.meta_json
                }
                for event in recent_events
            ],
            'recent_leads': [
                {
                    'id': lead.id,
                    'first_name': lead.first_name,
                    'last_name': lead.last_name,
                    'company_name': lead.company_name,
                    'status': lead.status,
                    'created_at': lead.created_at.isoformat(),
                    'campaign_id': lead.campaign_id
                }
                for lead in recent_leads
            ],
            'active_campaigns': [
                {
                    'id': campaign.id,
                    'name': campaign.name,
                    'client_id': campaign.client_id,
                    'status': campaign.status
                }
                for campaign in active_campaigns
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting real-time activity: {str(e)}")
        return jsonify({'error': str(e)}), 500
