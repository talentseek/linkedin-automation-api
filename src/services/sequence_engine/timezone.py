"""
Timezone handling and working day calculations.

This module contains functionality for:
- Campaign timezone management
- Working day calculations
- Weekend detection
- Timezone-aware date operations
"""

import logging
from datetime import datetime, timedelta
import calendar
import pytz
from src.models import Campaign

logger = logging.getLogger(__name__)


def _get_campaign_timezone(self, campaign: Campaign) -> pytz.timezone:
    """Get the timezone for a campaign."""
    try:
        return pytz.timezone(campaign.timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Unknown timezone '{campaign.timezone}' for campaign {campaign.id}, using UTC")
        return pytz.UTC


def _get_campaign_local_time(self, campaign: Campaign) -> datetime:
    """Get the current local time for a campaign's timezone."""
    tz = self._get_campaign_timezone(campaign)
    utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    return utc_now.astimezone(tz)


def _is_weekend_in_timezone(self, campaign: Campaign, date: datetime = None) -> bool:
    """Check if a date falls on a weekend in the campaign's timezone."""
    if date is None:
        local_time = self._get_campaign_local_time(campaign)
    else:
        # Convert UTC date to campaign timezone
        tz = self._get_campaign_timezone(campaign)
        if date.tzinfo is None:
            date = date.replace(tzinfo=pytz.UTC)
        local_time = date.astimezone(tz)
    
    return local_time.weekday() >= 5  # Saturday = 5, Sunday = 6


def _add_working_days_in_timezone(self, campaign: Campaign, start_date: datetime, working_days: int) -> datetime:
    """Add working days to a date in the campaign's timezone, skipping weekends."""
    if working_days <= 0:
        return start_date
    
    tz = self._get_campaign_timezone(campaign)
    
    # Convert start_date to campaign timezone
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=pytz.UTC)
    current_date = start_date.astimezone(tz)
    days_added = 0
    
    while days_added < working_days:
        current_date += timedelta(days=1)
        
        # Skip weekends
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            days_added += 1
    
    # Convert back to UTC
    return current_date.astimezone(pytz.UTC).replace(tzinfo=None)


def _get_next_working_day(self, campaign: Campaign, start_date: datetime = None) -> datetime:
    """Get the next working day in the campaign's timezone."""
    if start_date is None:
        start_date = datetime.utcnow()
    
    tz = self._get_campaign_timezone(campaign)
    
    # Convert to campaign timezone
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=pytz.UTC)
    current_date = start_date.astimezone(tz)
    
    # Find next working day
    while current_date.weekday() >= 5:  # Weekend
        current_date += timedelta(days=1)
    
    # Convert back to UTC
    return current_date.astimezone(pytz.UTC).replace(tzinfo=None)


def _get_working_days_between(self, campaign: Campaign, start_date: datetime, end_date: datetime) -> int:
    """Calculate the number of working days between two dates in the campaign's timezone."""
    tz = self._get_campaign_timezone(campaign)
    
    # Convert dates to campaign timezone
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=pytz.UTC)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=pytz.UTC)
    
    start_local = start_date.astimezone(tz)
    end_local = end_date.astimezone(tz)
    
    # Calculate working days
    working_days = 0
    current_date = start_local
    
    while current_date <= end_local:
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            working_days += 1
        current_date += timedelta(days=1)
    
    return working_days


def _is_business_hours(self, campaign: Campaign, date: datetime = None) -> bool:
    """Check if a date/time is within business hours in the campaign's timezone."""
    if date is None:
        local_time = self._get_campaign_local_time(campaign)
    else:
        # Convert UTC date to campaign timezone
        tz = self._get_campaign_timezone(campaign)
        if date.tzinfo is None:
            date = date.replace(tzinfo=pytz.UTC)
        local_time = date.astimezone(tz)
    
    # Check if it's a working day
    if local_time.weekday() >= 5:  # Weekend
        return False
    
    # Check if it's within business hours (9 AM - 5 PM)
    hour = local_time.hour
    return 9 <= hour < 17
