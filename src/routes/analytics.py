import logging
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required

from src.models import db, Campaign, Lead, Event
from src.models.rate_usage import RateUsage


logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__)


def _daterange(days: int):
    today = datetime.utcnow().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _bucket_events_by_day(events):
    buckets = defaultdict(list)
    for ev in events:
        if not ev.timestamp:
            continue
        day = ev.timestamp.date()
        buckets[day].append(ev)
    return buckets


@analytics_bp.route("/campaigns/<campaign_id>/summary", methods=["GET"])
@jwt_required()
def campaign_summary(campaign_id: str):
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        # Lead status breakdown
        lead_stats = defaultdict(int)
        for lead in campaign.leads:
            lead_stats[lead.status] += 1

        # Last activity
        last_event = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id)
            .order_by(Event.timestamp.desc())
            .first()
        )
        last_activity_at = last_event.timestamp.isoformat() if last_event and last_event.timestamp else None

        # Last 7 days time series for invites/messages
        days_param = request.args.get("days", default=7, type=int)
        since = datetime.utcnow() - timedelta(days=days_param)
        recent_events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
            .all()
        )

        buckets = _bucket_events_by_day(recent_events)
        days = _daterange(days_param)
        invites_per_day = OrderedDict()
        messages_per_day = OrderedDict()
        for d in days:
            day_events = buckets.get(d, [])
            invites_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "connection_request_sent")
            messages_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_sent")

        return jsonify(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "total_leads": len(campaign.leads),
                "lead_statistics": dict(lead_stats),
                "last_activity_at": last_activity_at,
                "last_n_days": days_param,
                "invites_sent_per_day": invites_per_day,
                "messages_sent_per_day": messages_per_day,
            }
        ), 200
    except Exception as e:
        logger.error(f"Error in campaign_summary: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/campaigns/<campaign_id>/timeseries", methods=["GET"])
@jwt_required()
def campaign_timeseries(campaign_id: str):
    try:
        days = request.args.get("days", default=30, type=int)
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        since = datetime.utcnow() - timedelta(days=days)
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
            .all()
        )

        buckets = _bucket_events_by_day(events)
        day_keys = _daterange(days)
        timeseries = OrderedDict()
        for d in day_keys:
            day_events = buckets.get(d, [])
            timeseries[d.isoformat()] = {
                "invites": sum(1 for e in day_events if e.event_type == "connection_request_sent"),
                "messages": sum(1 for e in day_events if e.event_type == "message_sent"),
                "replies": sum(1 for e in day_events if e.event_type == "message_received"),
                "connections": sum(
                    1
                    for e in day_events
                    if e.event_type in ("connection_accepted", "connection_accepted_historical")
                ),
            }

        return jsonify({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "days": days,
            "timeseries": timeseries,
        }), 200
    except Exception as e:
        logger.error(f"Error in campaign_timeseries: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/accounts/<linkedin_account_id>/rate-usage", methods=["GET"])
@jwt_required()
def account_rate_usage(linkedin_account_id: str):
    try:
        days = request.args.get("days", default=7, type=int)
        since = datetime.utcnow() - timedelta(days=days)

        # Prefer persisted usage if available; fallback to events
        day_keys = _daterange(days)
        invites = OrderedDict()
        messages = OrderedDict()

        rows = (
            db.session.query(RateUsage)
            .filter(RateUsage.linkedin_account_id == linkedin_account_id, RateUsage.usage_date >= since.date())
            .all()
        )
        by_day = {r.usage_date: r for r in rows}

        if rows:
            for d in day_keys:
                r = by_day.get(d)
                invites[d.isoformat()] = (r.invites_sent if r else 0)
                messages[d.isoformat()] = (r.messages_sent if r else 0)
        else:
            # Fallback to events if no persisted usage
            events = (
                db.session.query(Event)
                .filter(Event.timestamp >= since)
                .order_by(Event.timestamp.desc())
                .all()
            )
            filtered = [e for e in events if (e.meta_json or {}).get("linkedin_account_id") == linkedin_account_id]
            buckets = _bucket_events_by_day(filtered)
            for d in day_keys:
                day_events = buckets.get(d, [])
                invites[d.isoformat()] = sum(1 for e in day_events if e.event_type == "connection_request_sent")
                messages[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_sent")

        # Limits from config
        invites_limit = int(current_app.config.get("MAX_CONNECTIONS_PER_DAY", 25))
        messages_limit = int(current_app.config.get("MAX_MESSAGES_PER_DAY", 100))

        return jsonify({
            "linkedin_account_id": linkedin_account_id,
            "days": days,
            "invites_sent_per_day": invites,
            "messages_sent_per_day": messages,
            "limits": {
                "invites_per_day": invites_limit,
                "messages_per_day": messages_limit,
            },
        }), 200
    except Exception as e:
        logger.error(f"Error in account_rate_usage: {str(e)}")
        return jsonify({"error": str(e)}), 500


