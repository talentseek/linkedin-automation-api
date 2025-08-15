"""
Campaign-specific analytics endpoints.

This module contains functionality for:
- Campaign summary analytics
- Campaign timeseries data
- First-level connections analytics
- Rate usage analytics
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from flask import jsonify, request, current_app
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import joinedload

from src.extensions import db
from src.models import Campaign, Lead, Event, LinkedInAccount, Client
from src.models.rate_usage import RateUsage
from .core import _calculate_conversion_funnel, _calculate_time_based_analytics, _calculate_predictive_analytics

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import analytics_bp


@analytics_bp.route("/campaigns/<campaign_id>/summary", methods=["GET"])
def campaign_summary(campaign_id):
    """Get comprehensive analytics summary for a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get basic campaign stats
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        total_leads = len(leads)
        
        # Calculate status breakdown
        status_counts = {}
        for lead in leads:
            status = lead.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get recent events
        recent_events = Event.query.join(Lead).filter(
            Lead.campaign_id == campaign_id,
            Event.timestamp >= datetime.utcnow() - timedelta(days=7)
        ).order_by(desc(Event.timestamp)).limit(10).all()
        
        # Calculate conversion funnel
        conversion_funnel = _calculate_conversion_funnel(campaign_id)
        
        # Calculate time-based analytics
        time_analytics = _calculate_time_based_analytics(campaign_id)
        
        # Calculate predictive analytics
        predictive_analytics = _calculate_predictive_analytics(campaign_id)
        
        # Get LinkedIn account info
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        summary = {
            'campaign': {
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat(),
                'timezone': campaign.timezone
            },
            'overview': {
                'total_leads': total_leads,
                'status_breakdown': status_counts,
                'recent_events': [
                    {
                        'id': event.id,
                        'event_type': event.event_type,
                        'timestamp': event.timestamp.isoformat(),
                        'lead_id': event.lead_id
                    }
                    for event in recent_events
                ]
            },
            'conversion_funnel': conversion_funnel,
            'time_analytics': time_analytics,
            'predictive_analytics': predictive_analytics,
            'linkedin_account': {
                'account_id': linkedin_account.account_id if linkedin_account else None,
                'status': linkedin_account.status if linkedin_account else None
            }
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting campaign summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route("/campaigns/<campaign_id>/timeseries", methods=["GET"])
def campaign_timeseries(campaign_id):
    """Get timeseries data for a campaign."""
    try:
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        event_type = request.args.get('event_type')
        
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Build query
        query = Event.query.join(Lead).filter(
            Lead.campaign_id == campaign_id,
            Event.timestamp >= start_date
        )
        
        if event_type:
            query = query.filter(Event.event_type == event_type)
        
        events = query.order_by(asc(Event.timestamp)).all()
        
        # Bucket events by day
        buckets = _bucket_events_by_day(events)
        
        # Generate timeseries data
        timeseries_data = []
        for day in _daterange(days):
            day_events = buckets.get(day, [])
            
            # Count by event type
            event_counts = {}
            for event in day_events:
                event_type = event.event_type
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            timeseries_data.append({
                'date': day.isoformat(),
                'total_events': len(day_events),
                'event_breakdown': event_counts
            })
        
        return jsonify({
            'campaign_id': campaign_id,
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'timeseries_data': timeseries_data
        })
        
    except Exception as e:
        logger.error(f"Error getting campaign timeseries: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route("/campaigns/<campaign_id>/first-level-connections", methods=["GET"])
def campaign_first_level_connections(campaign_id):
    """Get analytics for first-level connections in a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get first-level connection leads
        first_level_leads = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.connection_type == '1st Level'
        ).all()
        
        # Calculate metrics
        total_first_level = len(first_level_leads)
        connected_first_level = len([l for l in first_level_leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
        responded_first_level = len([l for l in first_level_leads if l.status in ['responded', 'completed']])
        
        # Calculate rates
        connection_rate = (connected_first_level / total_first_level * 100) if total_first_level > 0 else 0
        response_rate = (responded_first_level / total_first_level * 100) if total_first_level > 0 else 0
        
        # Get recent first-level events
        recent_events = Event.query.join(Lead).filter(
            Lead.campaign_id == campaign_id,
            Lead.connection_type == '1st Level',
            Event.timestamp >= datetime.utcnow() - timedelta(days=7)
        ).order_by(desc(Event.timestamp)).limit(10).all()
        
        return jsonify({
            'campaign_id': campaign_id,
            'metrics': {
                'total_first_level_leads': total_first_level,
                'connected_first_level': connected_first_level,
                'responded_first_level': responded_first_level,
                'connection_rate': round(connection_rate, 2),
                'response_rate': round(response_rate, 2)
            },
            'recent_events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(),
                    'lead_id': event.lead_id
                }
                for event in recent_events
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting first-level connections analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route("/accounts/<linkedin_account_id>/rate-usage", methods=["GET"])
def account_rate_usage(linkedin_account_id):
    """Get rate usage analytics for a LinkedIn account."""
    try:
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get rate usage data
        usage_records = RateUsage.query.filter(
            RateUsage.provider_account_id == linkedin_account_id,
            RateUsage.date >= start_date,
            RateUsage.date <= end_date
        ).order_by(asc(RateUsage.date)).all()
        
        # Generate daily usage data
        daily_usage = []
        for day in _daterange(days):
            # Find usage record for this day
            usage_record = next((r for r in usage_records if r.date == day), None)
            
            daily_usage.append({
                'date': day.isoformat(),
                'connections_sent': usage_record.connections_sent if usage_record else 0,
                'messages_sent': usage_record.messages_sent if usage_record else 0,
                'total_actions': (usage_record.connections_sent + usage_record.messages_sent) if usage_record else 0
            })
        
        # Calculate totals
        total_connections = sum(day['connections_sent'] for day in daily_usage)
        total_messages = sum(day['messages_sent'] for day in daily_usage)
        total_actions = sum(day['total_actions'] for day in daily_usage)
        
        return jsonify({
            'linkedin_account_id': linkedin_account_id,
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'totals': {
                'total_connections': total_connections,
                'total_messages': total_messages,
                'total_actions': total_actions
            },
            'daily_usage': daily_usage
        })
        
    except Exception as e:
        logger.error(f"Error getting rate usage analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500
