"""
Health check and status endpoints.

This module contains endpoints for:
- Webhook health checks
- System status monitoring
- Webhook data retrieval
"""

import logging
from flask import request, jsonify
from src.models import db, WebhookData
from src.routes.webhook import webhook_bp
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@webhook_bp.route('/webhook/health', methods=['GET'])
def webhook_health():
    """Health check endpoint for webhooks."""
    try:
        # Check database connectivity
        db.session.execute('SELECT 1')
        
        # Get recent webhook activity
        recent_webhooks = WebhookData.query.filter(
            WebhookData.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'recent_webhooks_24h': recent_webhooks,
            'message': 'Webhook system is operational'
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e),
            'message': 'Webhook system is experiencing issues'
        }), 500


@webhook_bp.route('/webhook/data', methods=['GET'])
def get_webhook_data():
    """Get recent webhook data for debugging."""
    try:
        # Get query parameters
        limit = request.args.get('limit', default=50, type=int)
        hours = request.args.get('hours', default=24, type=int)
        
        # Query recent webhook data
        since_time = datetime.utcnow() - timedelta(hours=hours)
        webhook_data = WebhookData.query.filter(
            WebhookData.created_at >= since_time
        ).order_by(WebhookData.created_at.desc()).limit(limit).all()
        
        # Format response
        data = []
        for webhook in webhook_data:
            data.append({
                'id': webhook.id,
                'created_at': webhook.created_at.isoformat(),
                'event_type': webhook.event_type,
                'payload_size': len(webhook.payload) if webhook.payload else 0,
                'headers': webhook.headers,
                'processed': webhook.processed
            })
        
        return jsonify({
            'total': len(data),
            'since': since_time.isoformat(),
            'webhooks': data
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving webhook data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/status', methods=['GET'])
def webhook_status():
    """Get comprehensive webhook system status."""
    try:
        # Get various status metrics
        total_webhooks = WebhookData.query.count()
        
        # Recent activity (last 24 hours)
        recent_24h = WebhookData.query.filter(
            WebhookData.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Recent activity (last hour)
        recent_1h = WebhookData.query.filter(
            WebhookData.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        # Processed vs unprocessed
        processed_count = WebhookData.query.filter_by(processed=True).count()
        unprocessed_count = WebhookData.query.filter_by(processed=False).count()
        
        # Event type breakdown
        from sqlalchemy import func
        event_types = db.session.query(
            WebhookData.event_type,
            func.count(WebhookData.id).label('count')
        ).group_by(WebhookData.event_type).all()
        
        event_breakdown = {event_type: count for event_type, count in event_types}
        
        return jsonify({
            'status': 'operational',
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {
                'total_webhooks': total_webhooks,
                'recent_24h': recent_24h,
                'recent_1h': recent_1h,
                'processed': processed_count,
                'unprocessed': unprocessed_count
            },
            'event_types': event_breakdown,
            'system': {
                'database': 'connected',
                'webhook_processing': 'active'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500
