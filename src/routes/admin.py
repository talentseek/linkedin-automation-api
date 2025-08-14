from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import inspect, text

from src.extensions import db
from src.services.scheduler import get_outreach_scheduler


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


