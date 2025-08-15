"""
Notification management endpoints.

This module contains functionality for:
- Notification settings
- Notification testing
- Weekly statistics testing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, current_app

from src.services.notifications import NotificationService
from src.services.weekly_statistics import WeeklyStatisticsService

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import automation_bp


@automation_bp.route('/notifications/settings', methods=['GET'])
def get_notification_settings():
    """Get notification settings."""
    try:
        settings = {
            'enabled': current_app.config.get('NOTIFICATIONS_ENABLED', True),
            'from_email': current_app.config.get('NOTIFY_EMAIL_FROM', 'notifications@notifications.costperdemo.com'),
            'to_email': current_app.config.get('NOTIFY_EMAIL_TO'),
            'resend_api_key_configured': bool(current_app.config.get('RESEND_API_KEY')),
            'weekly_stats_enabled': current_app.config.get('WEEKLY_STATS_ENABLED', True)
        }
        
        return jsonify(settings)
        
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/notifications/test', methods=['POST'])
def test_notifications():
    """Test notification sending."""
    try:
        data = request.get_json() or {}
        test_email = data.get('test_email')
        
        if not test_email:
            return jsonify({'error': 'test_email is required'}), 400
        
        # Initialize notification service
        notification_service = NotificationService()
        
        # Send test notification
        result = notification_service.send_notification(
            subject="Test Notification",
            message="This is a test notification from the LinkedIn Automation API.",
            to_email=test_email
        )
        
        return jsonify({
            'message': 'Test notification sent successfully',
            'test_email': test_email,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error testing notifications: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/notifications/simple-test', methods=['POST'])
def test_simple_notification():
    """Send a simple test notification."""
    try:
        data = request.get_json() or {}
        test_email = data.get('test_email')
        subject = data.get('subject', 'Simple Test Notification')
        message = data.get('message', 'This is a simple test notification.')
        
        if not test_email:
            return jsonify({'error': 'test_email is required'}), 400
        
        # Initialize notification service
        notification_service = NotificationService()
        
        # Send simple notification
        result = notification_service.send_notification(
            subject=subject,
            message=message,
            to_email=test_email
        )
        
        return jsonify({
            'message': 'Simple test notification sent successfully',
            'test_email': test_email,
            'subject': subject,
            'message_sent': message,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error sending simple test notification: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/weekly-stats/test-simple', methods=['POST'])
def test_weekly_stats_simple():
    """Test weekly statistics generation and sending."""
    try:
        data = request.get_json() or {}
        client_id = data.get('client_id')
        test_email = data.get('test_email')
        
        if not client_id:
            return jsonify({'error': 'client_id is required'}), 400
        
        # Initialize weekly statistics service
        weekly_stats_service = WeeklyStatisticsService()
        
        # Generate statistics
        stats = weekly_stats_service.generate_client_statistics(client_id)
        
        if not stats:
            return jsonify({
                'client_id': client_id,
                'message': 'No data available for this client'
            })
        
        # Test email sending if test_email provided
        email_result = None
        if test_email:
            try:
                email_result = weekly_stats_service.send_weekly_report(
                    client_id, 
                    stats, 
                    test_email=test_email
                )
            except Exception as e:
                email_result = {'error': str(e)}
        
        return jsonify({
            'client_id': client_id,
            'statistics': stats,
            'email_result': email_result,
            'test': True
        })
        
    except Exception as e:
        logger.error(f"Error testing weekly stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
