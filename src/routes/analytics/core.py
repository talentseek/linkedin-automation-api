"""
Core analytics functionality.

This module contains the main analytics blueprint and core functionality:
- Analytics blueprint registration
- Common helper functions
- Core analytics endpoints
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import joinedload

from src.extensions import db
from src.models import Campaign, Lead, Event, LinkedInAccount, Client
from src.services.weekly_statistics import WeeklyStatisticsService

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import analytics_bp


def _daterange(days: int):
    """Generate a list of dates for the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def _bucket_events_by_day(events):
    """Group events by day for timeseries analysis."""
    buckets = {}
    for event in events:
        day = event.timestamp.date()
        if day not in buckets:
            buckets[day] = []
        buckets[day].append(event)
    return buckets


def _calculate_conversion_funnel(campaign_id, days=30):
    """Calculate conversion funnel for a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return None
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all leads for the campaign
        leads = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.created_at >= start_date
        ).all()
        
        # Calculate funnel stages
        total_leads = len(leads)
        invites_sent = len([l for l in leads if l.status in ['invite_sent', 'invited']])
        connected = len([l for l in leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
        messaged = len([l for l in leads if l.status in ['messaged', 'responded', 'completed']])
        responded = len([l for l in leads if l.status in ['responded', 'completed']])
        completed = len([l for l in leads if l.status == 'completed'])
        
        # Calculate conversion rates
        invite_rate = (invites_sent / total_leads * 100) if total_leads > 0 else 0
        connect_rate = (connected / total_leads * 100) if total_leads > 0 else 0
        message_rate = (messaged / total_leads * 100) if total_leads > 0 else 0
        response_rate = (responded / total_leads * 100) if total_leads > 0 else 0
        completion_rate = (completed / total_leads * 100) if total_leads > 0 else 0
        
        return {
            'funnel_stages': {
                'total_leads': total_leads,
                'invites_sent': invites_sent,
                'connected': connected,
                'messaged': messaged,
                'responded': responded,
                'completed': completed
            },
            'conversion_rates': {
                'invite_rate': round(invite_rate, 2),
                'connect_rate': round(connect_rate, 2),
                'message_rate': round(message_rate, 2),
                'response_rate': round(response_rate, 2),
                'completion_rate': round(completion_rate, 2)
            },
            'stage_conversions': {
                'invite_to_connect': round((connected / invites_sent * 100) if invites_sent > 0 else 0, 2),
                'connect_to_message': round((messaged / connected * 100) if connected > 0 else 0, 2),
                'message_to_response': round((responded / messaged * 100) if messaged > 0 else 0, 2),
                'response_to_completion': round((completed / responded * 100) if responded > 0 else 0, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating conversion funnel: {str(e)}")
        return None


def _calculate_time_based_analytics(campaign_id, days=30):
    """Calculate time-based analytics for a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return None
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get events for the campaign
        events = Event.query.join(Lead).filter(
            Lead.campaign_id == campaign_id,
            Event.timestamp >= start_date
        ).all()
        
        # Analyze hourly patterns
        hourly_replies = {}
        for event in events:
            if event.event_type == 'message_received':
                hour = event.timestamp.hour
                if hour not in hourly_replies:
                    hourly_replies[hour] = 0
                hourly_replies[hour] += 1
        
        # Find optimal sending times
        optimal_hours = sorted(hourly_replies.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Calculate response times
        response_times = []
        for event in events:
            if event.event_type == 'message_sent':
                # Find next reply within 7 days
                next_reply = Event.query.join(Lead).filter(
                    Lead.campaign_id == campaign_id,
                    Event.event_type == 'message_received',
                    Event.timestamp > event.timestamp,
                    Event.timestamp <= event.timestamp + timedelta(days=7)
                ).first()
                
                if next_reply:
                    response_time = (next_reply.timestamp - event.timestamp).total_seconds() / 3600  # hours
                    response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'hourly_analysis': {
                'hourly_replies': hourly_replies,
                'optimal_sending_hours': [hour for hour, count in optimal_hours]
            },
            'response_analysis': {
                'average_response_time_hours': round(avg_response_time, 2),
                'total_responses': len(response_times),
                'response_rate': round((len(response_times) / len([e for e in events if e.event_type == 'message_sent']) * 100) if events else 0, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating time-based analytics: {str(e)}")
        return None


def _calculate_predictive_analytics(campaign_id):
    """Calculate predictive analytics for a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return None
        
        # Get campaign data
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        total_leads = len(leads)
        
        if total_leads == 0:
            return None
        
        # Calculate current performance
        connected_leads = len([l for l in leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
        responded_leads = len([l for l in leads if l.status in ['responded', 'completed']])
        
        # Calculate rates
        connection_rate = connected_leads / total_leads
        response_rate = responded_leads / total_leads if total_leads > 0 else 0
        
        # Predict completion
        estimated_completions = int(total_leads * response_rate * 0.3)  # Assume 30% of responses convert
        
        # Calculate campaign completion estimate
        if campaign.status == 'active':
            # Estimate based on current pace
            days_active = (datetime.utcnow() - campaign.created_at).days
            if days_active > 0:
                leads_per_day = total_leads / days_active
                estimated_days_to_completion = max(0, (estimated_completions - responded_leads) / leads_per_day)
            else:
                estimated_days_to_completion = 30  # Default estimate
        else:
            estimated_days_to_completion = 0
        
        return {
            'performance_metrics': {
                'connection_rate': round(connection_rate * 100, 2),
                'response_rate': round(response_rate * 100, 2),
                'current_completions': responded_leads,
                'estimated_completions': estimated_completions
            },
            'predictions': {
                'estimated_days_to_completion': round(estimated_days_to_completion, 1),
                'completion_probability': round(response_rate * 100, 2),
                'campaign_health': 'good' if response_rate > 0.05 else 'needs_attention'
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating predictive analytics: {str(e)}")
        return None
