"""
Campaign start/stop/pause functionality.

This module contains functionality for:
- Starting campaigns
- Pausing campaigns
- Getting campaign status
- Rate limit checking
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any
from flask import jsonify, request, current_app
from sqlalchemy import func, and_, or_, desc, asc

from src.extensions import db
from src.models.rate_usage import RateUsage
from src.models import Campaign, Lead, Event, LinkedInAccount, Client

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import automation_bp


def _get_rate_limit_status(linkedin_account_id: str) -> dict:
    """Compute today's rate limit usage and remaining quotas for a LinkedIn account.

    Reads persisted counts from `RateUsage` and uses app-configured limits.
    """
    try:
        today = date.today()

        usage = RateUsage.query.filter_by(
            linkedin_account_id=linkedin_account_id,
            usage_date=today,
        ).first()

        invites_sent = usage.invites_sent if usage else 0
        messages_sent = usage.messages_sent if usage else 0

        max_connections_per_day = current_app.config.get('MAX_CONNECTIONS_PER_DAY', 25)
        max_messages_per_day = current_app.config.get('MAX_MESSAGES_PER_DAY', 100)

        return {
            'linkedin_account_id': linkedin_account_id,
            'date': today.isoformat(),
            'invites_sent': invites_sent,
            'messages_sent': messages_sent,
            'limits': {
                'max_connections_per_day': max_connections_per_day,
                'max_messages_per_day': max_messages_per_day,
            },
            'remaining': {
                'invites': max(max_connections_per_day - invites_sent, 0),
                'messages': max(max_messages_per_day - messages_sent, 0),
            },
        }
    except Exception as e:
        logger.error(f"Error computing rate limit status: {str(e)}")
        return {'error': str(e)}


@automation_bp.route('/campaigns/<campaign_id>/start', methods=['POST'])
def start_campaign(campaign_id):
    """Start a campaign automation."""
    try:
        # Validate campaign automation
        validation = _validate_campaign_automation(campaign_id)
        if not validation['valid']:
            return jsonify({'error': validation['error']}), 400
        
        campaign = validation['campaign']
        
        # Check if campaign is already active
        if campaign.status == 'active':
            return jsonify({'message': 'Campaign is already active'}), 200
        
        # Update campaign status
        campaign.status = 'active'
        campaign.started_at = datetime.utcnow()
        
        # Create event
        event = Event(
            event_type='campaign_started',
            lead_id=None,
            meta_json={
                'campaign_id': campaign_id,
                'started_at': campaign.started_at.isoformat()
            }
        )
        
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"Campaign {campaign_id} started successfully")
        
        return jsonify({
            'message': 'Campaign started successfully',
            'campaign_id': campaign_id,
            'status': 'active',
            'started_at': campaign.started_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting campaign: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/campaigns/<campaign_id>/pause', methods=['POST'])
def pause_campaign(campaign_id):
    """Pause a campaign automation."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check if campaign is already paused
        if campaign.status == 'paused':
            return jsonify({'message': 'Campaign is already paused'}), 200
        
        # Update campaign status
        old_status = campaign.status
        campaign.status = 'paused'
        campaign.paused_at = datetime.utcnow()
        
        # Create event
        event = Event(
            event_type='campaign_paused',
            lead_id=None,
            meta_json={
                'campaign_id': campaign_id,
                'previous_status': old_status,
                'paused_at': campaign.paused_at.isoformat()
            }
        )
        
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"Campaign {campaign_id} paused successfully")
        
        return jsonify({
            'message': 'Campaign paused successfully',
            'campaign_id': campaign_id,
            'status': 'paused',
            'paused_at': campaign.paused_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error pausing campaign: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/campaigns/<campaign_id>/status', methods=['GET'])
def get_campaign_status(campaign_id):
    """Get the current status of a campaign."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get lead statistics
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
        
        # Get LinkedIn account info
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        # Get rate limit status if LinkedIn account exists
        rate_limit_status = None
        if linkedin_account:
            rate_limit_status = _get_rate_limit_status(linkedin_account.account_id)
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'status': campaign.status,
            'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
            'statistics': {
                'total_leads': total_leads,
                'status_breakdown': status_counts
            },
            'recent_events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(),
                    'lead_id': event.lead_id
                }
                for event in recent_events
            ],
            'linkedin_account': {
                'account_id': linkedin_account.account_id if linkedin_account else None,
                'status': linkedin_account.status if linkedin_account else None
            },
            'rate_limit_status': rate_limit_status
        })
        
    except Exception as e:
        logger.error(f"Error getting campaign status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/rate-limits/<linkedin_account_id>', methods=['GET'])
def get_rate_limits(linkedin_account_id):
    """Get rate limit status for a LinkedIn account."""
    try:
        rate_limit_status = _get_rate_limit_status(linkedin_account_id)
        
        if 'error' in rate_limit_status:
            return jsonify(rate_limit_status), 500
        
        return jsonify(rate_limit_status)
        
    except Exception as e:
        logger.error(f"Error getting rate limits: {str(e)}")
        return jsonify({'error': str(e)}), 500
