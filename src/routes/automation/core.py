"""
Core automation functionality.

This module contains the main automation blueprint and core functionality:
- Automation blueprint registration
- Common helper functions
- Core automation endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func, and_, or_, desc, asc

from src.extensions import db
from src.models import Campaign, Lead, Event, LinkedInAccount, Client
from src.services.scheduler import get_outreach_scheduler
from src.services.sequence_engine import SequenceEngine

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import automation_bp


def _get_scheduler_status():
    """Get the current status of the outreach scheduler."""
    try:
        scheduler = get_outreach_scheduler()
        return {
            'running': scheduler.running,
            'thread_alive': scheduler.thread.is_alive() if scheduler.thread else False,
            'last_reset_date': scheduler.last_reset_date.isoformat() if scheduler.last_reset_date else None
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return {'error': str(e)}


def _validate_campaign_automation(campaign_id):
    """Validate that a campaign can be automated."""
    try:
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return {'valid': False, 'error': 'Campaign not found'}
        
        # Check if campaign has a LinkedIn account
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            return {'valid': False, 'error': 'No connected LinkedIn account for this campaign'}
        
        # Check if campaign has a sequence
        if not campaign.sequence_json:
            return {'valid': False, 'error': 'Campaign has no sequence defined'}
        
        # Check if campaign has leads
        lead_count = Lead.query.filter_by(campaign_id=campaign_id).count()
        if lead_count == 0:
            return {'valid': False, 'error': 'Campaign has no leads'}
        
        return {
            'valid': True,
            'campaign': campaign,
            'linkedin_account': linkedin_account,
            'lead_count': lead_count
        }
        
    except Exception as e:
        logger.error(f"Error validating campaign automation: {str(e)}")
        return {'valid': False, 'error': str(e)}


def _get_rate_limit_status(linkedin_account_id):
    """Get rate limit status for a LinkedIn account."""
    try:
        from src.models.rate_usage import RateUsage
        
        # Get today's usage
        today = datetime.utcnow().date()
        usage = RateUsage.query.filter_by(
            provider_account_id=linkedin_account_id,
            date=today
        ).first()
        
        if not usage:
            usage = RateUsage(
                provider_account_id=linkedin_account_id,
                date=today,
                connections_sent=0,
                messages_sent=0
            )
            db.session.add(usage)
            db.session.commit()
        
        # Get rate limits from config
        max_connections = current_app.config.get('MAX_CONNECTIONS_PER_DAY', 25)
        max_messages = current_app.config.get('MAX_MESSAGES_PER_DAY', 100)
        
        return {
            'linkedin_account_id': linkedin_account_id,
            'date': today.isoformat(),
            'connections_sent': usage.connections_sent,
            'messages_sent': usage.messages_sent,
            'max_connections': max_connections,
            'max_messages': max_messages,
            'connections_remaining': max(0, max_connections - usage.connections_sent),
            'messages_remaining': max(0, max_messages - usage.messages_sent),
            'connections_limit_reached': usage.connections_sent >= max_connections,
            'messages_limit_reached': usage.messages_sent >= max_messages
        }
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {str(e)}")
        return {'error': str(e)}
