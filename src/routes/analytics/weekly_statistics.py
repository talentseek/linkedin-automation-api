"""
Weekly statistics and reporting endpoints.

This module contains functionality for:
- Weekly statistics generation
- Weekly report sending
- Statistics preview
- Statistics settings
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, current_app

from src.extensions import db
from src.models import Campaign, Lead, Event, Client
from src.services.weekly_statistics import WeeklyStatisticsService

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import analytics_bp


@analytics_bp.route('/weekly-stats/generate', methods=['POST'])
def generate_weekly_statistics():
    """Generate weekly statistics for all clients."""
    try:
        data = request.get_json() or {}
        force_regenerate = data.get('force_regenerate', False)
        
        # Initialize weekly statistics service
        weekly_stats_service = WeeklyStatisticsService()
        
        # Get all clients
        clients = Client.query.all()
        
        results = []
        for client in clients:
            try:
                # Generate statistics for this client (last 7 days)
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=7)
                stats = weekly_stats_service.generate_client_statistics(client.id, start_date, end_date)
                
                if stats:
                    results.append({
                        'client_id': client.id,
                        'client_name': client.name,
                        'status': 'success',
                        'statistics': stats
                    })
                else:
                    results.append({
                        'client_id': client.id,
                        'client_name': client.name,
                        'status': 'no_data',
                        'message': 'No data available for this client'
                    })
                    
            except Exception as e:
                logger.error(f"Error generating statistics for client {client.id}: {str(e)}")
                results.append({
                    'client_id': client.id,
                    'client_name': client.name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'message': 'Weekly statistics generation completed',
            'total_clients': len(clients),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error generating weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/send-all', methods=['POST'])
def send_all_weekly_reports():
    """Send weekly reports to all clients."""
    try:
        data = request.get_json() or {}
        force_send = data.get('force_send', False)
        
        # Initialize weekly statistics service
        weekly_stats_service = WeeklyStatisticsService()
        
        # Send all weekly reports
        result = weekly_stats_service.send_all_weekly_reports()
        
        return jsonify({
            'message': 'Weekly reports sent successfully',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error sending weekly reports: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/preview/<client_id>', methods=['GET'])
def preview_weekly_statistics(client_id):
    """Preview weekly statistics for a specific client."""
    try:
        # Get client
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Initialize weekly statistics service
        weekly_stats_service = WeeklyStatisticsService()
        
        # Generate statistics for preview (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        stats = weekly_stats_service.generate_client_statistics(client_id, start_date, end_date)
        
        if not stats:
            return jsonify({
                'client_id': client_id,
                'client_name': client.name,
                'message': 'No data available for this client'
            })
        
        return jsonify({
            'client_id': client_id,
            'client_name': client.name,
            'statistics': stats,
            'preview': True
        })
        
    except Exception as e:
        logger.error(f"Error previewing weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/settings', methods=['GET'])
def get_weekly_stats_settings():
    """Get weekly statistics settings."""
    try:
        # Get settings from environment
        settings = {
            'enabled': current_app.config.get('WEEKLY_STATS_ENABLED', True),
            'send_day': 'monday',  # Default to Monday
            'send_time': '09:00',  # Default to 9 AM
            'timezone': 'UTC',
            'email_template': 'default',
            'include_charts': True,
            'include_comparisons': True
        }
        
        return jsonify(settings)
        
    except Exception as e:
        logger.error(f"Error getting weekly stats settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/test', methods=['POST'])
def test_weekly_statistics():
    """Test weekly statistics generation and email sending."""
    try:
        data = request.get_json() or {}
        client_id = data.get('client_id')
        test_email = data.get('test_email')
        
        if not client_id:
            return jsonify({'error': 'client_id is required'}), 400
        
        # Get client
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Initialize weekly statistics service
        weekly_stats_service = WeeklyStatisticsService()
        
        # Generate statistics (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        stats = weekly_stats_service.generate_client_statistics(client_id, start_date, end_date)
        
        if not stats:
            return jsonify({
                'client_id': client_id,
                'client_name': client.name,
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
            'client_name': client.name,
            'statistics': stats,
            'email_result': email_result,
            'test': True
        })
        
    except Exception as e:
        logger.error(f"Error testing weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500
