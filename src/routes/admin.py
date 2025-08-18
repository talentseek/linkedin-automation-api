import logging
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import inspect, text, func

from src.extensions import db
from src.services.scheduler import get_outreach_scheduler
from src.models import Lead, Event, Campaign, Client, LinkedInAccount, WebhookData

logger = logging.getLogger(__name__)


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/migrations/status", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def migrations_status():
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        leads_cols = [c["name"] for c in inspector.get_columns("leads")] if "leads" in tables else []
        has_rate_usage = "rate_usage" in tables
        has_conversation_id = "conversation_id" in leads_cols
        return jsonify({
            "tables": tables,
            "has_rate_usage": has_rate_usage,
            "has_leads_conversation_id": has_conversation_id,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/migrations/bootstrap", methods=["POST"])
# @jwt_required()  # Temporarily removed for development
def migrations_bootstrap():
    """Idempotent bootstrap to ensure critical schema exists in production.

    - Adds leads.conversation_id if missing
    - Creates rate_usage table if missing
    """
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        changes = []

        # Ensure leads.conversation_id exists
        if "leads" in tables:
            lead_cols = [c["name"] for c in inspector.get_columns("leads")]
            if "conversation_id" not in lead_cols:
                db.session.execute(text("ALTER TABLE leads ADD COLUMN conversation_id VARCHAR(255)"))
                changes.append("added leads.conversation_id")
        else:
            return jsonify({"error": "leads table not found"}), 500

        # Ensure rate_usage table exists
        if "rate_usage" not in tables:
            db.session.execute(text(
                """
                CREATE TABLE rate_usage (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  linkedin_account_id VARCHAR(64) NOT NULL,
                  usage_date DATE NOT NULL,
                  invites_sent INTEGER NOT NULL DEFAULT 0,
                  messages_sent INTEGER NOT NULL DEFAULT 0
                );
                """
            ))
            # Unique index
            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_rate_usage_account_date ON rate_usage(linkedin_account_id, usage_date)"
            ))
            # Supporting indexes
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_rate_usage_account ON rate_usage(linkedin_account_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_rate_usage_date ON rate_usage(usage_date)"))
            changes.append("created rate_usage table and indexes")

        db.session.commit()
        return jsonify({
            "message": "Bootstrap migrations applied",
            "changes": changes
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/backfill/conversations", methods=["POST"])
# @jwt_required()  # Temporarily removed for development
def backfill_conversations():
    """Run the conversation_id backfill immediately (one-off)."""
    try:
        scheduler = get_outreach_scheduler()
        if not scheduler:
            return jsonify({"error": "scheduler unavailable"}), 500
        # Execute synchronously
        scheduler._run_conversation_id_backfill()
        return jsonify({"message": "Conversation ID backfill triggered"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/backfill/rate-usage", methods=["POST"])
# @jwt_required()  # Temporarily removed for development
def backfill_rate_usage():
    """Run the rate usage backfill immediately for yesterday (UTC)."""
    try:
        scheduler = get_outreach_scheduler()
        if not scheduler:
            return jsonify({"error": "scheduler unavailable"}), 500
        # Execute synchronously
        scheduler._run_rate_usage_backfill()
        return jsonify({"message": "Rate usage backfill (yesterday UTC) triggered"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Performance Optimization Endpoints

@admin_bp.route("/performance/optimize-database", methods=["POST"])
# @jwt_required()  # Temporarily removed for development
def optimize_database():
    """Run database optimization (indexes, statistics)."""
    try:
        from src.optimization.database_indexes import optimize_database as run_optimization
        
        start_time = time.time()
        results = run_optimization()
        end_time = time.time()
        
        return jsonify({
            'message': 'Database optimization completed successfully',
            'execution_time_seconds': round(end_time - start_time, 2),
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Database optimization failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route("/performance/query-stats", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def get_query_stats():
    """Get database query performance statistics."""
    try:
        # Get table sizes
        table_sizes = {}
        tables = ['leads', 'events', 'campaigns', 'clients', 'linkedin_accounts', 'webhook_data', 'rate_usage']
        
        for table in tables:
            try:
                result = db.session.execute(text(f"SELECT COUNT(*) as count FROM {table}")).fetchone()
                table_sizes[table] = result[0] if result else 0
            except Exception as e:
                logger.warning(f"Could not get count for table {table}: {str(e)}")
                table_sizes[table] = 0
        
        # Get recent activity (last 24 hours)
        recent_events = Event.query.filter(
            Event.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        recent_leads = Lead.query.filter(
            Lead.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Get index information
        index_info = {}
        for table in tables:
            try:
                result = db.session.execute(text(f"""
                    SELECT indexname, indexdef 
                    FROM pg_indexes 
                    WHERE tablename = '{table}'
                    ORDER BY indexname
                """)).fetchall()
                index_info[table] = [{'name': row[0], 'definition': row[1]} for row in result]
            except Exception as e:
                logger.warning(f"Could not get index info for table {table}: {str(e)}")
                index_info[table] = []
        
        return jsonify({
            'table_sizes': table_sizes,
            'recent_activity_24h': {
                'events': recent_events,
                'leads': recent_leads
            },
            'indexes': index_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get query stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route("/performance/slow-queries", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def get_slow_queries():
    """Get information about potentially slow queries."""
    try:
        # Analyze common query patterns
        slow_query_patterns = []
        
        # Check for leads without proper indexes
        try:
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM leads 
                WHERE status IN ('pending_invite', 'connected') 
                AND last_step_sent_at IS NULL
            """)).fetchone()
            
            if result and result[0] > 1000:
                slow_query_patterns.append({
                    'type': 'large_lead_scan',
                    'description': f"Large lead scan: {result[0]} leads without last_step_sent_at",
                    'impact': 'high',
                    'recommendation': 'Add index on (status, last_step_sent_at)'
                })
        except Exception as e:
            logger.warning(f"Could not analyze lead scan: {str(e)}")
        
        # Check for events without proper indexes
        try:
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM events 
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """)).fetchone()
            
            if result and result[0] > 10000:
                slow_query_patterns.append({
                    'type': 'large_event_scan',
                    'description': f"Large event scan: {result[0]} events in last 24 hours",
                    'impact': 'medium',
                    'recommendation': 'Add index on timestamp'
                })
        except Exception as e:
            logger.warning(f"Could not analyze event scan: {str(e)}")
        
        # Check for campaigns without proper indexes
        try:
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM campaigns 
                WHERE status = 'active'
            """)).fetchone()
            
            if result and result[0] > 100:
                slow_query_patterns.append({
                    'type': 'large_campaign_scan',
                    'description': f"Large campaign scan: {result[0]} active campaigns",
                    'impact': 'low',
                    'recommendation': 'Add index on status'
                })
        except Exception as e:
            logger.warning(f"Could not analyze campaign scan: {str(e)}")
        
        return jsonify({
            'slow_query_patterns': slow_query_patterns,
            'total_patterns': len(slow_query_patterns),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to analyze slow queries: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route("/performance/connection-pool", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def get_connection_pool_stats():
    """Get database connection pool statistics."""
    try:
        # Get basic connection info
        engine = db.engine
        
        pool_stats = {
            'pool_size': engine.pool.size(),
            'checked_in': engine.pool.checkedin(),
            'checked_out': engine.pool.checkedout(),
            'overflow': engine.pool.overflow()
        }
        
        return jsonify({
            'connection_pool': pool_stats,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get connection pool stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


