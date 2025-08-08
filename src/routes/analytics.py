import logging
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required

from src.models import db, Campaign, Lead, Event, LinkedInAccount
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

        # Last 7 days time series for invites/messages/replies
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
        replies_per_day = OrderedDict()
        for d in days:
            day_events = buckets.get(d, [])
            invites_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "connection_request_sent")
            messages_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_sent")
            replies_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_received")

        # Aggregate reply metrics over the period
        total_messages_period = sum(messages_per_day.values())
        total_replies_period = sum(replies_per_day.values())
        reply_rate_period = (total_replies_period / total_messages_period) if total_messages_period else 0.0

        # Time to first reply metrics over the period (in days)
        from statistics import mean, median
        tfr_days = []
        try:
            # For each lead with a reply in period, compute difference from first message_sent to first message_received
            by_lead_events = defaultdict(list)
            for ev in recent_events:
                by_lead_events[ev.lead_id].append(ev)
            for lead_id, evs in by_lead_events.items():
                msgs = sorted([e for e in evs if e.event_type == "message_sent"], key=lambda e: e.timestamp)
                reps = sorted([e for e in evs if e.event_type == "message_received"], key=lambda e: e.timestamp)
                if msgs and reps:
                    dt = (reps[0].timestamp - msgs[0].timestamp).total_seconds() / 86400.0
                    if dt >= 0:
                        tfr_days.append(dt)
        except Exception:
            pass
        tfr_avg = mean(tfr_days) if tfr_days else 0.0
        tfr_median = median(tfr_days) if tfr_days else 0.0

        # Reply distribution by step (which message elicited the reply)
        reply_distribution = OrderedDict()
        try:
            # Initialize for first three steps
            for k in ("step_1", "step_2", "step_3", "unknown"):
                reply_distribution[k] = 0
            for lead_id, evs in by_lead_events.items():
                msgs = sorted([e for e in evs if e.event_type == "message_sent"], key=lambda e: e.timestamp)
                reps = sorted([e for e in evs if e.event_type == "message_received"], key=lambda e: e.timestamp)
                if not reps:
                    continue
                first_reply_ts = reps[0].timestamp
                # Count messages sent before first reply
                index = 0
                for m in msgs:
                    if m.timestamp and m.timestamp <= first_reply_ts:
                        index += 1
                # index is number of messages sent up to and including first reply time
                if index == 0:
                    reply_distribution["unknown"] += 1
                elif index == 1:
                    reply_distribution["step_1"] += 1
                elif index == 2:
                    reply_distribution["step_2"] += 1
                elif index >= 3:
                    reply_distribution["step_3"] += 1
        except Exception:
            pass

        # Per-account reply rates over the period
        per_account = OrderedDict()
        try:
            # Map provider account_id -> LinkedInAccount.id
            acct_map = {}
            for acct in LinkedInAccount.query.all():
                if acct.account_id:
                    acct_map[acct.account_id] = acct.id
            msg_counts = defaultdict(int)
            rep_counts = defaultdict(int)
            for ev in recent_events:
                if ev.event_type == "message_sent":
                    acct_id = (ev.meta_json or {}).get("linkedin_account_id")
                    if acct_id:
                        msg_counts[acct_id] += 1
                elif ev.event_type == "message_received":
                    prov_acct = (ev.meta_json or {}).get("account_id")
                    acct_id = acct_map.get(prov_acct)
                    if acct_id:
                        rep_counts[acct_id] += 1
            acct_keys = sorted(set(list(msg_counts.keys()) + list(rep_counts.keys())))
            for aid in acct_keys:
                m = msg_counts.get(aid, 0)
                r = rep_counts.get(aid, 0)
                per_account[aid] = {
                    "messages": m,
                    "replies": r,
                    "reply_rate": (r / m) if m else 0.0,
                }
        except Exception:
            pass

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
                "replies_received_per_day": replies_per_day,
                "reply_count_last_n_days": total_replies_period,
                "reply_rate_last_n_days": reply_rate_period,
                "time_to_first_reply_days_avg": tfr_avg,
                "time_to_first_reply_days_median": tfr_median,
                "reply_distribution_by_step": reply_distribution,
                "per_account_reply_rates": per_account,
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


