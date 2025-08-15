"""
Delay calculations and timing logic.

This module contains functionality for:
- Delay calculation between steps
- Working day delay logic
- Minimum delay enforcement
- Timing validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from src.models import Campaign

logger = logging.getLogger(__name__)


def _calculate_delay(self, step: Dict[str, Any], campaign: Campaign = None) -> timedelta:
    """Calculate the delay for a step based on its configuration."""
    try:
        # Get delay configuration
        delay_hours = step.get('delay_hours', 0)
        delay_working_days = step.get('delay_working_days', 0)
        
        # Calculate total delay
        total_delay = timedelta(hours=delay_hours)
        
        # Add working days delay if campaign timezone is available
        if campaign and delay_working_days > 0:
            # Calculate working days delay
            working_days_delay = self._calculate_working_days_delay(campaign, delay_working_days)
            total_delay += working_days_delay
        
        return total_delay
        
    except Exception as e:
        logger.error(f"Error calculating delay: {str(e)}")
        return timedelta(hours=24)  # Default to 24 hours


def _calculate_working_days_delay(self, campaign: Campaign, working_days: int) -> timedelta:
    """Calculate delay in working days for a campaign."""
    try:
        if working_days <= 0:
            return timedelta(0)
        
        # Get current time in campaign timezone
        current_time = self._get_campaign_local_time(campaign)
        
        # Calculate target date by adding working days
        target_date = self._add_working_days_in_timezone(campaign, current_time, working_days)
        
        # Calculate the difference
        delay = target_date - current_time.replace(tzinfo=None)
        
        return delay
        
    except Exception as e:
        logger.error(f"Error calculating working days delay: {str(e)}")
        # Fallback: assume 8 hours per working day
        return timedelta(hours=working_days * 8)


def _get_minimum_delay(self, step: Dict[str, Any], campaign: Campaign = None) -> timedelta:
    """Get the minimum delay for a step."""
    try:
        # Get minimum delay configuration
        min_delay_hours = step.get('min_delay_hours', 0)
        min_delay_working_days = step.get('min_delay_working_days', 0)
        
        # Calculate minimum delay
        min_delay = timedelta(hours=min_delay_hours)
        
        # Add minimum working days delay if campaign timezone is available
        if campaign and min_delay_working_days > 0:
            min_working_days_delay = self._calculate_working_days_delay(campaign, min_delay_working_days)
            min_delay += min_working_days_delay
        
        return min_delay
        
    except Exception as e:
        logger.error(f"Error calculating minimum delay: {str(e)}")
        return timedelta(0)


def _add_working_days(self, start_date: datetime, working_days: int) -> datetime:
    """Add working days to a date, skipping weekends."""
    try:
        if working_days <= 0:
            return start_date
        
        current_date = start_date
        days_added = 0
        
        while days_added < working_days:
            current_date += timedelta(days=1)
            
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                days_added += 1
        
        return current_date
        
    except Exception as e:
        logger.error(f"Error adding working days: {str(e)}")
        return start_date + timedelta(days=working_days)


def _validate_timing(self, step: Dict[str, Any], campaign: Campaign = None) -> Dict[str, Any]:
    """Validate the timing configuration of a step."""
    try:
        errors = []
        warnings = []
        
        # Check delay configuration
        delay_hours = step.get('delay_hours', 0)
        delay_working_days = step.get('delay_working_days', 0)
        
        if delay_hours < 0:
            errors.append("delay_hours cannot be negative")
        
        if delay_working_days < 0:
            errors.append("delay_working_days cannot be negative")
        
        # Check for reasonable delays
        if delay_hours > 168:  # More than 1 week
            warnings.append("delay_hours is very long (>1 week)")
        
        if delay_working_days > 30:  # More than 6 weeks
            warnings.append("delay_working_days is very long (>6 weeks)")
        
        # Check for immediate execution
        if delay_hours == 0 and delay_working_days == 0:
            warnings.append("Step will execute immediately (no delay)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating timing: {str(e)}")
        return {
            'valid': False,
            'errors': [str(e)],
            'warnings': []
        }


def _get_next_execution_time(self, step: Dict[str, Any], campaign: Campaign, last_execution: datetime = None) -> datetime:
    """Calculate the next execution time for a step."""
    try:
        if last_execution is None:
            last_execution = datetime.utcnow()
        
        # Calculate delay
        delay = self._calculate_delay(step, campaign)
        
        # Add delay to last execution time
        next_execution = last_execution + delay
        
        # Ensure it's not in the past
        if next_execution < datetime.utcnow():
            next_execution = datetime.utcnow()
        
        return next_execution
        
    except Exception as e:
        logger.error(f"Error calculating next execution time: {str(e)}")
        return datetime.utcnow() + timedelta(hours=24)  # Default to 24 hours from now
