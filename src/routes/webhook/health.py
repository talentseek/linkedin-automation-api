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
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        # Get recent webhook activity
        recent_webhooks = WebhookData.query.filter(
            WebhookData.timestamp >= datetime.utcnow() - timedelta(hours=24)
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
            WebhookData.timestamp >= since_time
        ).order_by(WebhookData.timestamp.desc()).limit(limit).all()
        
        # Format response
        data = []
        for webhook in webhook_data:
            data.append({
                'id': webhook.id,
                'timestamp': webhook.timestamp.isoformat(),
                'method': webhook.method,
                'url': webhook.url,
                'content_type': webhook.content_type,
                'content_length': webhook.content_length
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
            WebhookData.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Recent activity (last hour)
        recent_1h = WebhookData.query.filter(
            WebhookData.timestamp >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        # Method breakdown
        from sqlalchemy import func
        method_types = db.session.query(
            WebhookData.method,
            func.count(WebhookData.id).label('count')
        ).group_by(WebhookData.method).all()
        
        method_breakdown = {method: count for method, count in method_types}
        
        return jsonify({
            'status': 'operational',
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {
                'total_webhooks': total_webhooks,
                'recent_24h': recent_24h,
                'recent_1h': recent_1h
            },
            'method_breakdown': method_breakdown,
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
