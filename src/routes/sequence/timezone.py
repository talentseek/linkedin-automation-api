"""
Timezone-related sequence operations.

This module contains functionality for:
- Campaign timezone management
- Timezone information retrieval
- Available timezones listing
"""

import logging
import pytz
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from src.extensions import db
from src.models import Campaign

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import sequence_bp


@sequence_bp.route('/campaigns/<campaign_id>/timezone', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_campaign_timezone_info(campaign_id):
    """Get timezone information for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        timezone = campaign.timezone or 'UTC'
        
        # Get timezone info
        tz = pytz.timezone(timezone)
        current_time = tz.localize(datetime.utcnow())
        
        return jsonify({
            'campaign_id': campaign_id,
            'timezone': timezone,
            'current_time': current_time.isoformat(),
            'timezone_offset': current_time.utcoffset().total_seconds() / 3600,
            'is_dst': current_time.dst() != timedelta(0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign timezone info: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/campaigns/<campaign_id>/timezone', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
def update_campaign_timezone(campaign_id):
    """Update the timezone for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        if not data or 'timezone' not in data:
            return jsonify({'error': 'Timezone is required'}), 400
        
        timezone = data['timezone']
        
        # Validate timezone
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            return jsonify({'error': 'Invalid timezone'}), 400
        
        # Update campaign timezone
        campaign.timezone = timezone
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign timezone updated successfully',
            'campaign_id': campaign_id,
            'timezone': timezone
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating campaign timezone: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/timezones', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_available_timezones():
    """Get a list of available timezones."""
    try:
        # Get common timezones
        common_timezones = [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Australia/Sydney'
        ]
        
        # Get all timezones
        all_timezones = pytz.all_timezones
        
        return jsonify({
            'common_timezones': common_timezones,
            'all_timezones': all_timezones,
            'total_count': len(all_timezones)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting available timezones: {str(e)}")
        return jsonify({'error': str(e)}), 500
