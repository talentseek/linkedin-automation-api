"""
Scheduler management endpoints.

This module contains functionality for:
- Scheduler status checking
- Starting scheduler
- Stopping scheduler
- Weekend status checking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, current_app

from src.services.scheduler import get_outreach_scheduler

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import automation_bp


@automation_bp.route('/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get the current status of the outreach scheduler."""
    try:
        scheduler = get_outreach_scheduler()
        
        status = {
            'running': scheduler.running,
            'thread_alive': scheduler.thread.is_alive() if scheduler.thread else False,
            'last_reset_date': scheduler.last_reset_date.isoformat() if scheduler.last_reset_date else None,
            'max_connections_per_day': scheduler.max_connections_per_day,
            'max_messages_per_day': scheduler.max_messages_per_day,
            'min_delay_between_actions': scheduler.min_delay_between_actions,
            'max_delay_between_actions': scheduler.max_delay_between_actions,
            'working_hours_start': scheduler.working_hours_start,
            'working_hours_end': scheduler.working_hours_end,
            'nightly_hour_utc': scheduler.nightly_hour_utc
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    """Start the outreach scheduler."""
    try:
        scheduler = get_outreach_scheduler()
        
        if scheduler.running:
            return jsonify({'message': 'Scheduler is already running'}), 200
        
        scheduler.start()
        
        return jsonify({
            'message': 'Scheduler started successfully',
            'status': 'running'
        })
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """Stop the outreach scheduler."""
    try:
        scheduler = get_outreach_scheduler()
        
        if not scheduler.running:
            return jsonify({'message': 'Scheduler is already stopped'}), 200
        
        scheduler.stop()
        
        return jsonify({
            'message': 'Scheduler stopped successfully',
            'status': 'stopped'
        })
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/weekend-status', methods=['GET'])
def get_weekend_status():
    """Check if current time is weekend (when scheduler skips processing)."""
    try:
        scheduler = get_outreach_scheduler()
        
        # Check if it's weekend
        is_weekend = scheduler._is_weekend()
        
        current_time = datetime.utcnow()
        
        return jsonify({
            'current_time': current_time.isoformat(),
            'is_weekend': is_weekend,
            'weekday': current_time.strftime('%A'),
            'weekday_number': current_time.weekday(),
            'scheduler_skips_weekends': True
        })
        
    except Exception as e:
        logger.error(f"Error getting weekend status: {str(e)}")
        return jsonify({'error': str(e)}), 500
