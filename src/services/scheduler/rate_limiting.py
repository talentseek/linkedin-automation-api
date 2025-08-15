"""
Rate limiting and usage tracking functionality.

This module contains functionality for:
- Rate limit checking
- Usage tracking
- Daily counters management
"""

import logging
from datetime import datetime, date
from src.models import db, RateUsage
from src.models.linkedin_account import LinkedInAccount

logger = logging.getLogger(__name__)


def _get_today_usage_counts(self, provider_account_id: str):
    """Get today's usage counts for a specific account."""
    try:
        today = date.today()
        
        # Get today's usage record
        usage = RateUsage.query.filter_by(
            provider_account_id=provider_account_id,
            date=today
        ).first()
        
        if not usage:
            # Create new usage record for today
            usage = RateUsage(
                provider_account_id=provider_account_id,
                date=today,
                connections_sent=0,
                messages_sent=0
            )
            db.session.add(usage)
            db.session.commit()
        
        return usage.connections_sent, usage.messages_sent
        
    except Exception as e:
        logger.error(f"Error getting usage counts: {str(e)}")
        return 0, 0


def _can_send_invite_for_account(self, provider_account_id: str) -> bool:
    """Check if we can send an invite for the given account."""
    try:
        connections_sent, _ = self._get_today_usage_counts(provider_account_id)
        return connections_sent < self.max_connections_per_day
        
    except Exception as e:
        logger.error(f"Error checking invite rate limit: {str(e)}")
        return False


def _can_send_message_for_account(self, provider_account_id: str, is_first_level: bool) -> bool:
    """Check if we can send a message for the given account."""
    try:
        _, messages_sent = self._get_today_usage_counts(provider_account_id)
        
        # First level connections have higher limits
        if is_first_level:
            return messages_sent < self.max_messages_per_day
        else:
            # For non-first level, use a lower limit
            return messages_sent < (self.max_messages_per_day // 2)
        
    except Exception as e:
        logger.error(f"Error checking message rate limit: {str(e)}")
        return False


def _increment_usage(self, provider_account_id: str, action_type: str):
    """Increment usage counter for a specific action."""
    try:
        today = date.today()
        
        # Get or create today's usage record
        usage = RateUsage.query.filter_by(
            provider_account_id=provider_account_id,
            date=today
        ).first()
        
        if not usage:
            usage = RateUsage(
                provider_account_id=provider_account_id,
                date=today,
                connections_sent=0,
                messages_sent=0
            )
            db.session.add(usage)
        
        # Increment the appropriate counter
        if action_type == 'connection':
            usage.connections_sent += 1
        elif action_type == 'message':
            usage.messages_sent += 1
        
        db.session.commit()
        
        logger.info(f"Incremented {action_type} usage for account {provider_account_id}")
        
    except Exception as e:
        logger.error(f"Error incrementing usage: {str(e)}")
        db.session.rollback()


def _reset_daily_counters(self):
    """Reset daily counters for all accounts."""
    try:
        today = date.today()
        
        # Get all LinkedIn accounts
        accounts = LinkedInAccount.query.filter_by(status='connected').all()
        
        for account in accounts:
            # Ensure today's usage record exists
            usage = RateUsage.query.filter_by(
                provider_account_id=account.account_id,
                date=today
            ).first()
            
            if not usage:
                usage = RateUsage(
                    provider_account_id=account.account_id,
                    date=today,
                    connections_sent=0,
                    messages_sent=0
                )
                db.session.add(usage)
        
        db.session.commit()
        logger.info("Daily counters reset for all accounts")
        
    except Exception as e:
        logger.error(f"Error resetting daily counters: {str(e)}")
        db.session.rollback()
