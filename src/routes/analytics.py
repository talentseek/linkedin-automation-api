import logging
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
import csv
import io
import json

from flask import Blueprint, jsonify, request, current_app, send_file
from flask_jwt_extended import jwt_required

from src.models import db, Campaign, Lead, Event, LinkedInAccount, Client
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


def _calculate_conversion_funnel(campaign_id, days=30):
    """Calculate conversion funnel metrics for a campaign."""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get all leads for the campaign
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        
        # Get events for the period
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign_id, Event.timestamp >= since)
            .all()
        )
        
        # Calculate funnel metrics
        total_leads = len(leads)
        invites_sent = sum(1 for e in events if e.event_type == "connection_request_sent")
        connections_made = sum(1 for e in events if e.event_type in ["connection_accepted", "connection_accepted_historical"])
        messages_sent = sum(1 for e in events if e.event_type == "message_sent")
        replies_received = sum(1 for e in events if e.event_type == "message_received")
        
        # Calculate conversion rates
        invite_to_connect_rate = (connections_made / invites_sent * 100) if invites_sent > 0 else 0
        connect_to_message_rate = (messages_sent / connections_made * 100) if connections_made > 0 else 0
        message_to_reply_rate = (replies_received / messages_sent * 100) if messages_sent > 0 else 0
        overall_conversion_rate = (replies_received / total_leads * 100) if total_leads > 0 else 0
        
        return {
            "total_leads": total_leads,
            "invites_sent": invites_sent,
            "connections_made": connections_made,
            "messages_sent": messages_sent,
            "replies_received": replies_received,
            "conversion_rates": {
                "invite_to_connect": round(invite_to_connect_rate, 2),
                "connect_to_message": round(connect_to_message_rate, 2),
                "message_to_reply": round(message_to_reply_rate, 2),
                "overall_conversion": round(overall_conversion_rate, 2)
            },
            "funnel_stages": [
                {"stage": "Total Leads", "count": total_leads, "percentage": 100},
                {"stage": "Invites Sent", "count": invites_sent, "percentage": round(invites_sent / total_leads * 100, 2) if total_leads > 0 else 0},
                {"stage": "Connections Made", "count": connections_made, "percentage": round(connections_made / total_leads * 100, 2) if total_leads > 0 else 0},
                {"stage": "Messages Sent", "count": messages_sent, "percentage": round(messages_sent / total_leads * 100, 2) if total_leads > 0 else 0},
                {"stage": "Replies Received", "count": replies_received, "percentage": round(replies_received / total_leads * 100, 2) if total_leads > 0 else 0}
            ]
        }
    except Exception as e:
        logger.error(f"Error calculating conversion funnel: {str(e)}")
        return None


def _calculate_time_based_analytics(campaign_id, days=30):
    """Calculate time-based analytics including optimal sending times."""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign_id, Event.timestamp >= since)
            .all()
        )
        
        # Group events by hour of day
        hourly_stats = defaultdict(lambda: {"sent": 0, "replies": 0})
        
        for event in events:
            if event.timestamp:
                hour = event.timestamp.hour
                if event.event_type == "message_sent":
                    hourly_stats[hour]["sent"] += 1
                elif event.event_type == "message_received":
                    hourly_stats[hour]["replies"] += 1
        
        # Calculate reply rates by hour
        hourly_reply_rates = {}
        for hour in range(24):
            sent = hourly_stats[hour]["sent"]
            replies = hourly_stats[hour]["replies"]
            rate = (replies / sent * 100) if sent > 0 else 0
            hourly_reply_rates[hour] = {
                "messages_sent": sent,
                "replies_received": replies,
                "reply_rate": round(rate, 2)
            }
        
        # Find optimal sending times (top 3 hours by reply rate)
        optimal_hours = sorted(
            [(hour, data["reply_rate"]) for hour, data in hourly_reply_rates.items() if data["messages_sent"] > 0],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        # Calculate average response time
        response_times = []
        by_lead_events = defaultdict(list)
        for ev in events:
            by_lead_events[ev.lead_id].append(ev)
        
        for lead_id, evs in by_lead_events.items():
            msgs = sorted([e for e in evs if e.event_type == "message_sent"], key=lambda e: e.timestamp)
            reps = sorted([e for e in evs if e.event_type == "message_received"], key=lambda e: e.timestamp)
            if msgs and reps:
                dt = (reps[0].timestamp - msgs[0].timestamp).total_seconds() / 3600.0  # hours
                if dt >= 0:
                    response_times.append(dt)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "hourly_reply_rates": hourly_reply_rates,
            "optimal_sending_hours": [
                {"hour": hour, "reply_rate": rate, "formatted_time": f"{hour:02d}:00"}
                for hour, rate in optimal_hours
            ],
            "average_response_time_hours": round(avg_response_time, 2),
            "response_time_analysis": {
                "fast_responses": len([t for t in response_times if t <= 1]),  # within 1 hour
                "medium_responses": len([t for t in response_times if 1 < t <= 24]),  # within 24 hours
                "slow_responses": len([t for t in response_times if t > 24])  # over 24 hours
            }
        }
    except Exception as e:
        logger.error(f"Error calculating time-based analytics: {str(e)}")
        return None


def _calculate_predictive_analytics(campaign_id):
    """Calculate predictive analytics for campaign performance."""
    try:
        # Get campaign data
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return None
        
        # Get historical performance
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign_id)
            .all()
        )
        
        total_leads = len(campaign.leads)
        total_messages = sum(1 for e in events if e.event_type == "message_sent")
        total_replies = sum(1 for e in events if e.event_type == "message_received")
        
        # Calculate historical reply rate
        historical_reply_rate = (total_replies / total_messages * 100) if total_messages > 0 else 0
        
        # Predict future performance
        remaining_leads = sum(1 for lead in campaign.leads if lead.status in ["pending_invite", "invite_sent", "connected"])
        predicted_messages = remaining_leads * 2  # Assume 2 messages per lead on average
        predicted_replies = predicted_messages * (historical_reply_rate / 100)
        
        # Calculate campaign completion estimate
        avg_messages_per_day = total_messages / 30 if total_messages > 0 else 0  # Assume 30 days of data
        days_to_completion = predicted_messages / avg_messages_per_day if avg_messages_per_day > 0 else 0
        
        return {
            "historical_performance": {
                "total_leads": total_leads,
                "total_messages": total_messages,
                "total_replies": total_replies,
                "reply_rate": round(historical_reply_rate, 2)
            },
            "predictions": {
                "remaining_leads": remaining_leads,
                "predicted_messages": round(predicted_messages, 0),
                "predicted_replies": round(predicted_replies, 0),
                "predicted_reply_rate": round(historical_reply_rate, 2),
                "days_to_completion": round(days_to_completion, 1)
            },
            "confidence_metrics": {
                "data_points": total_messages,
                "confidence_level": "high" if total_messages > 50 else "medium" if total_messages > 20 else "low"
            }
        }
    except Exception as e:
        logger.error(f"Error calculating predictive analytics: {str(e)}")
        return None


@analytics_bp.route("/campaigns/<campaign_id>/summary", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def campaign_summary(campaign_id: str):
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        # Lead status breakdown
        lead_stats = defaultdict(int)
        first_level_connections = 0
        regular_connections = 0
        
        for lead in campaign.leads:
            lead_stats[lead.status] += 1
            
            # Count 1st level vs regular connections
            if lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                first_level_connections += 1
            else:
                regular_connections += 1

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
        first_level_messages_per_day = OrderedDict()
        regular_messages_per_day = OrderedDict()
        
        for d in days:
            day_events = buckets.get(d, [])
            invites_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "connection_request_sent")
            messages_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_sent")
            replies_per_day[d.isoformat()] = sum(1 for e in day_events if e.event_type == "message_received")
            
            # Separate 1st level vs regular messages
            first_level_messages = 0
            regular_messages = 0
            for e in day_events:
                if e.event_type == "message_sent":
                    # Check if this is a 1st level connection message
                    lead = Lead.query.get(e.lead_id)
                    if lead and lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                        first_level_messages += 1
                    else:
                        regular_messages += 1
            
            first_level_messages_per_day[d.isoformat()] = first_level_messages
            regular_messages_per_day[d.isoformat()] = regular_messages

        # Aggregate reply metrics over the period
        total_messages_period = sum(messages_per_day.values())
        total_replies_period = sum(replies_per_day.values())
        reply_rate_period = (total_replies_period / total_messages_period) if total_messages_period else 0.0

        # Separate reply rates for 1st level vs regular connections
        first_level_replies = 0
        regular_replies = 0
        first_level_messages_total = 0
        regular_messages_total = 0
        
        for e in recent_events:
            if e.event_type == "message_sent":
                lead = Lead.query.get(e.lead_id)
                if lead and lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                    first_level_messages_total += 1
                else:
                    regular_messages_total += 1
            elif e.event_type == "message_received":
                lead = Lead.query.get(e.lead_id)
                if lead and lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                    first_level_replies += 1
                else:
                    regular_replies += 1
        
        first_level_reply_rate = (first_level_replies / first_level_messages_total) if first_level_messages_total else 0.0
        regular_reply_rate = (regular_replies / regular_messages_total) if regular_messages_total else 0.0

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

        # Enhanced analytics
        conversion_funnel = _calculate_conversion_funnel(campaign_id, days_param)
        time_analytics = _calculate_time_based_analytics(campaign_id, days_param)
        predictive_analytics = _calculate_predictive_analytics(campaign_id)

        return jsonify(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "total_leads": len(campaign.leads),
                "lead_statistics": dict(lead_stats),
                "connection_breakdown": {
                    "first_level_connections": first_level_connections,
                    "regular_connections": regular_connections,
                    "total_connections": first_level_connections + regular_connections
                },
                "last_activity_at": last_activity_at,
                "last_n_days": days_param,
                "invites_sent_per_day": invites_per_day,
                "messages_sent_per_day": messages_per_day,
                "first_level_messages_per_day": first_level_messages_per_day,
                "regular_messages_per_day": regular_messages_per_day,
                "replies_received_per_day": replies_per_day,
                "reply_count_last_n_days": total_replies_period,
                "reply_rate_last_n_days": reply_rate_period,
                "reply_rates_by_connection_type": {
                    "first_level_connections": {
                        "messages_sent": first_level_messages_total,
                        "replies_received": first_level_replies,
                        "reply_rate": first_level_reply_rate
                    },
                    "regular_connections": {
                        "messages_sent": regular_messages_total,
                        "replies_received": regular_replies,
                        "reply_rate": regular_reply_rate
                    }
                },
                "time_to_first_reply_days_avg": tfr_avg,
                "time_to_first_reply_days_median": tfr_median,
                "reply_distribution_by_step": reply_distribution,
                "per_account_reply_rates": per_account,
                # Enhanced analytics
                "conversion_funnel": conversion_funnel,
                "time_based_analytics": time_analytics,
                "predictive_analytics": predictive_analytics,
            }
        ), 200
    except Exception as e:
        logger.error(f"Error in campaign_summary: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/campaigns/<campaign_id>/timeseries", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
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
            
            # Separate 1st level vs regular messages
            first_level_messages = 0
            regular_messages = 0
            for e in day_events:
                if e.event_type == "message_sent":
                    # Check if this is a 1st level connection message
                    lead = Lead.query.get(e.lead_id)
                    if lead and lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                        first_level_messages += 1
                    else:
                        regular_messages += 1
            
            timeseries[d.isoformat()] = {
                "invites": sum(1 for e in day_events if e.event_type == "connection_request_sent"),
                "messages": sum(1 for e in day_events if e.event_type == "message_sent"),
                "first_level_messages": first_level_messages,
                "regular_messages": regular_messages,
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


@analytics_bp.route("/campaigns/<campaign_id>/first-level-connections", methods=["GET"])
# @jwt_required()  # Temporarily removed for development
def first_level_connections_analytics(campaign_id: str):
    """
    Dedicated analytics for 1st level connections to highlight their performance
    """
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        # Get all 1st level connections
        first_level_leads = [
            lead for lead in campaign.leads 
            if lead.meta_json and lead.meta_json.get('source') == 'first_level_connections'
        ]
        
        # Get all regular connections for comparison
        regular_leads = [
            lead for lead in campaign.leads 
            if not (lead.meta_json and lead.meta_json.get('source') == 'first_level_connections')
        ]

        # Status breakdown for 1st level connections
        first_level_status = defaultdict(int)
        for lead in first_level_leads:
            first_level_status[lead.status] += 1

        # Status breakdown for regular connections
        regular_status = defaultdict(int)
        for lead in regular_leads:
            regular_status[lead.status] += 1

        # Get events for 1st level connections
        first_level_lead_ids = [lead.id for lead in first_level_leads]
        first_level_events = (
            db.session.query(Event)
            .filter(Event.lead_id.in_(first_level_lead_ids))
            .all()
        ) if first_level_lead_ids else []

        # Get events for regular connections
        regular_lead_ids = [lead.id for lead in regular_leads]
        regular_events = (
            db.session.query(Event)
            .filter(Event.lead_id.in_(regular_lead_ids))
            .all()
        ) if regular_lead_ids else []

        # Calculate metrics for 1st level connections
        first_level_messages = sum(1 for e in first_level_events if e.event_type == "message_sent")
        first_level_replies = sum(1 for e in first_level_events if e.event_type == "message_received")
        first_level_reply_rate = (first_level_replies / first_level_messages) if first_level_messages else 0.0

        # Calculate metrics for regular connections
        regular_messages = sum(1 for e in regular_events if e.event_type == "message_sent")
        regular_replies = sum(1 for e in regular_events if e.event_type == "message_received")
        regular_reply_rate = (regular_replies / regular_messages) if regular_messages else 0.0

        # Time to first reply for 1st level connections
        first_level_tfr_days = []
        try:
            by_lead_events = defaultdict(list)
            for ev in first_level_events:
                by_lead_events[ev.lead_id].append(ev)
            
            for lead_id, evs in by_lead_events.items():
                msgs = sorted([e for e in evs if e.event_type == "message_sent"], key=lambda e: e.timestamp)
                reps = sorted([e for e in evs if e.event_type == "message_received"], key=lambda e: e.timestamp)
                if msgs and reps:
                    dt = (reps[0].timestamp - msgs[0].timestamp).total_seconds() / 86400.0
                    if dt >= 0:
                        first_level_tfr_days.append(dt)
        except Exception:
            pass

        from statistics import mean, median
        first_level_tfr_avg = mean(first_level_tfr_days) if first_level_tfr_days else 0.0
        first_level_tfr_median = median(first_level_tfr_days) if first_level_tfr_days else 0.0

        # Performance comparison
        performance_comparison = {
            "first_level_connections": {
                "total_leads": len(first_level_leads),
                "messages_sent": first_level_messages,
                "replies_received": first_level_replies,
                "reply_rate": first_level_reply_rate,
                "time_to_first_reply_avg_days": first_level_tfr_avg,
                "time_to_first_reply_median_days": first_level_tfr_median,
                "status_breakdown": dict(first_level_status)
            },
            "regular_connections": {
                "total_leads": len(regular_leads),
                "messages_sent": regular_messages,
                "replies_received": regular_replies,
                "reply_rate": regular_reply_rate,
                "status_breakdown": dict(regular_status)
            }
        }

        # Calculate advantages
        reply_rate_advantage = first_level_reply_rate - regular_reply_rate if regular_reply_rate > 0 else first_level_reply_rate
        efficiency_advantage = {
            "no_connection_requests_needed": len(first_level_leads),
            "direct_messaging_from_start": len(first_level_leads),
            "higher_rate_limits": "2x messaging limits",
            "faster_conversion_cycle": "Skip connection step"
        }

        return jsonify({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "first_level_connections_summary": {
                "total_imported": len(first_level_leads),
                "percentage_of_total": (len(first_level_leads) / len(campaign.leads) * 100) if campaign.leads else 0,
                "messages_sent": first_level_messages,
                "replies_received": first_level_replies,
                "reply_rate": first_level_reply_rate,
                "time_to_first_reply_avg_days": first_level_tfr_avg
            },
            "performance_comparison": performance_comparison,
            "advantages": efficiency_advantage,
            "reply_rate_advantage_vs_regular": reply_rate_advantage,
            "key_insights": {
                "immediate_messaging": "1st level connections can be messaged immediately",
                "no_connection_delay": "Skip the connection request step entirely",
                "higher_limits": "200 messages/day vs 100 for regular connections",
                "better_response_rates": f"{first_level_reply_rate:.1%} vs {regular_reply_rate:.1%} reply rate"
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in first_level_connections_analytics: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/accounts/<linkedin_account_id>/rate-usage", methods=["GET"])
# # @jwt_required()  # Temporarily removed for development  # Temporarily removed for rate usage check
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
        first_level_messages_limit = messages_limit * 2  # 2x limit for 1st level connections

        return jsonify({
            "linkedin_account_id": linkedin_account_id,
            "days": days,
            "invites_sent_per_day": invites,
            "messages_sent_per_day": messages,
            "limits": {
                "invites_per_day": invites_limit,
                "messages_per_day": messages_limit,
                "first_level_messages_per_day": first_level_messages_limit,
            },
            "rate_limit_info": {
                "note": "1st level connections have 2x messaging limits (no connection requests needed)",
                "first_level_advantage": "Direct messaging without connection requests"
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in account_rate_usage: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/weekly-stats/generate', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def generate_weekly_statistics():
    """Generate and send weekly statistics for a specific client."""
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        recipient_email = data.get('recipient_email')
        
        if not client_id:
            return jsonify({'error': 'client_id is required'}), 400
        
        from src.services.weekly_statistics import get_weekly_statistics_service
        
        service = get_weekly_statistics_service()
        success = service.send_weekly_report(client_id, recipient_email)
        
        if success:
            return jsonify({'message': 'Weekly report sent successfully'}), 200
        else:
            return jsonify({'error': 'Failed to send weekly report'}), 500
            
    except Exception as e:
        logger.error(f"Error generating weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/send-all', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def send_all_weekly_reports():
    """Send weekly reports to all active clients."""
    try:
        from src.services.weekly_statistics import get_weekly_statistics_service
        
        service = get_weekly_statistics_service()
        results = service.send_all_weekly_reports()
        
        successful = sum(results.values())
        total = len(results)
        
        return jsonify({
            'message': f'Sent weekly reports to {successful}/{total} clients',
            'results': results,
            'successful': successful,
            'total': total
        }), 200
        
    except Exception as e:
        logger.error(f"Error sending all weekly reports: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/preview/<client_id>', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def preview_weekly_statistics(client_id):
    """Preview weekly statistics for a client without sending email."""
    try:
        from datetime import datetime, timedelta
        from src.services.weekly_statistics import get_weekly_statistics_service
        
        # Calculate date range (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        service = get_weekly_statistics_service()
        stats = service.generate_client_statistics(client_id, start_date, end_date)
        
        if not stats:
            return jsonify({'error': 'Failed to generate statistics'}), 500
        
        return jsonify({
            'client': {
                'id': stats['client'].id,
                'name': stats['client'].name,
                'email': stats['client'].email
            },
            'period': {
                'start': stats['period']['start'].isoformat(),
                'end': stats['period']['end'].isoformat()
            },
            'summary': stats['summary'],
            'campaigns': [
                {
                    'id': campaign_stat['campaign'].id,
                    'name': campaign_stat['campaign'].name,
                    'status': campaign_stat['campaign'].status,
                    'total_leads': campaign_stat['total_leads'],
                    'connections': campaign_stat['connections'],
                    'replies': campaign_stat['replies'],
                    'conversion_rate': campaign_stat['conversion_rate']
                }
                for campaign_stat in stats['campaigns']
            ],
            'recent_activity': stats['recent_activity']
        }), 200
        
    except Exception as e:
        logger.error(f"Error previewing weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/settings', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_weekly_stats_settings():
    """Get weekly statistics settings."""
    try:
        from src.services.weekly_statistics import get_weekly_statistics_service
        
        service = get_weekly_statistics_service()
        
        return jsonify({
            'enabled': service.enabled,
            'from_email': service.from_email,
            'resend_configured': bool(service.resend_api_key)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting weekly stats settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/weekly-stats/test', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_weekly_statistics():
    """Test weekly statistics by sending a sample report."""
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        test_email = data.get('test_email', 'michael@costperdemo.com')
        
        if not client_id:
            return jsonify({'error': 'client_id is required'}), 400
        
        from src.services.weekly_statistics import get_weekly_statistics_service
        
        service = get_weekly_statistics_service()
        success = service.send_weekly_report(client_id, test_email)
        
        if success:
            return jsonify({
                'message': f'Test weekly report sent to {test_email}',
                'test_email': test_email
            }), 200
        else:
            return jsonify({'error': 'Failed to send test weekly report'}), 500
            
    except Exception as e:
        logger.error(f"Error testing weekly statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# EXPORT FUNCTIONALITY
# =============================================================================

@analytics_bp.route('/campaigns/<campaign_id>/export/csv', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def export_campaign_csv(campaign_id: str):
    """Export campaign data to CSV format."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404
        
        # Get export type
        export_type = request.args.get('type', 'leads')  # leads, events, analytics
        
        if export_type == 'leads':
            return _export_leads_csv(campaign)
        elif export_type == 'events':
            return _export_events_csv(campaign)
        elif export_type == 'analytics':
            return _export_analytics_csv(campaign)
        else:
            return jsonify({"error": "Invalid export type. Use 'leads', 'events', or 'analytics'"}), 400
            
    except Exception as e:
        logger.error(f"Error exporting campaign CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _export_leads_csv(campaign):
    """Export leads data to CSV."""
    try:
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Lead ID', 'First Name', 'Last Name', 'Company', 'Status', 
            'Current Step', 'Connection Type', 'Created At', 'Last Activity'
        ])
        
        # Write data
        for lead in campaign.leads:
            connection_type = '1st Level' if (lead.meta_json and lead.meta_json.get('source') == 'first_level_connections') else 'Regular'
            
            # Get last activity
            last_event = (
                db.session.query(Event)
                .filter(Event.lead_id == lead.id)
                .order_by(Event.timestamp.desc())
                .first()
            )
            last_activity = last_event.timestamp.isoformat() if last_event and last_event.timestamp else ''
            
            writer.writerow([
                lead.id,
                lead.first_name or '',
                lead.last_name or '',
                lead.company_name or '',
                lead.status,
                lead.current_step,
                connection_type,
                lead.created_at.isoformat() if lead.created_at else '',
                last_activity
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{campaign.name}_leads_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        logger.error(f"Error exporting leads CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _export_events_csv(campaign):
    """Export events data to CSV."""
    try:
        # Get date range
        days = request.args.get('days', default=30, type=int)
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get events
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
            .order_by(Event.timestamp.desc())
            .all()
        )
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Event ID', 'Lead ID', 'Lead Name', 'Event Type', 'Timestamp', 
            'Meta Data', 'LinkedIn Account'
        ])
        
        # Write data
        for event in events:
            lead = Lead.query.get(event.lead_id)
            lead_name = f"{lead.first_name} {lead.last_name}" if lead else 'Unknown'
            
            writer.writerow([
                event.id,
                event.lead_id,
                lead_name,
                event.event_type,
                event.timestamp.isoformat() if event.timestamp else '',
                json.dumps(event.meta_json) if event.meta_json else '',
                (event.meta_json or {}).get('linkedin_account_id', '')
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{campaign.name}_events_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        logger.error(f"Error exporting events CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _export_analytics_csv(campaign):
    """Export analytics data to CSV."""
    try:
        # Get analytics data
        days = request.args.get('days', default=30, type=int)
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get events for timeseries
        events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
            .all()
        )
        
        buckets = _bucket_events_by_day(events)
        days_range = _daterange(days)
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Date', 'Invites Sent', 'Messages Sent', 'Replies Received', 
            'Connections Made', '1st Level Messages', 'Regular Messages'
        ])
        
        # Write data
        for d in days_range:
            day_events = buckets.get(d, [])
            
            invites = sum(1 for e in day_events if e.event_type == "connection_request_sent")
            messages = sum(1 for e in day_events if e.event_type == "message_sent")
            replies = sum(1 for e in day_events if e.event_type == "message_received")
            connections = sum(1 for e in day_events if e.event_type in ["connection_accepted", "connection_accepted_historical"])
            
            # Separate 1st level vs regular messages
            first_level_messages = 0
            regular_messages = 0
            for e in day_events:
                if e.event_type == "message_sent":
                    lead = Lead.query.get(e.lead_id)
                    if lead and lead.meta_json and lead.meta_json.get('source') == 'first_level_connections':
                        first_level_messages += 1
                    else:
                        regular_messages += 1
            
            writer.writerow([
                d.isoformat(),
                invites,
                messages,
                replies,
                connections,
                first_level_messages,
                regular_messages
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{campaign.name}_analytics_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        logger.error(f"Error exporting analytics CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# COMPARATIVE ANALYTICS
# =============================================================================

@analytics_bp.route('/clients/<client_id>/comparative-analytics', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def client_comparative_analytics(client_id: str):
    """Get comparative analytics across all campaigns for a client."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Client not found"}), 404
        
        days = request.args.get('days', default=30, type=int)
        since = datetime.utcnow() - timedelta(days=days)
        
        campaigns_data = []
        
        for campaign in client.campaigns:
            # Get campaign events
            events = (
                db.session.query(Event)
                .join(Lead, Lead.id == Event.lead_id)
                .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
                .all()
            )
            
            # Calculate metrics
            total_leads = len(campaign.leads)
            total_messages = sum(1 for e in events if e.event_type == "message_sent")
            total_replies = sum(1 for e in events if e.event_type == "message_received")
            total_invites = sum(1 for e in events if e.event_type == "connection_request_sent")
            total_connections = sum(1 for e in events if e.event_type in ["connection_accepted", "connection_accepted_historical"])
            
            reply_rate = (total_replies / total_messages * 100) if total_messages > 0 else 0
            connection_rate = (total_connections / total_invites * 100) if total_invites > 0 else 0
            
            campaigns_data.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'status': campaign.status,
                'total_leads': total_leads,
                'total_messages': total_messages,
                'total_replies': total_replies,
                'total_invites': total_invites,
                'total_connections': total_connections,
                'reply_rate': round(reply_rate, 2),
                'connection_rate': round(connection_rate, 2),
                'messages_per_lead': round(total_messages / total_leads, 2) if total_leads > 0 else 0,
                'replies_per_lead': round(total_replies / total_leads, 2) if total_leads > 0 else 0
            })
        
        # Calculate averages
        if campaigns_data:
            avg_reply_rate = sum(c['reply_rate'] for c in campaigns_data) / len(campaigns_data)
            avg_connection_rate = sum(c['connection_rate'] for c in campaigns_data) / len(campaigns_data)
            avg_messages_per_lead = sum(c['messages_per_lead'] for c in campaigns_data) / len(campaigns_data)
            avg_replies_per_lead = sum(c['replies_per_lead'] for c in campaigns_data) / len(campaigns_data)
        else:
            avg_reply_rate = avg_connection_rate = avg_messages_per_lead = avg_replies_per_lead = 0
        
        # Find best performing campaigns
        best_reply_rate = max(campaigns_data, key=lambda x: x['reply_rate']) if campaigns_data else None
        best_connection_rate = max(campaigns_data, key=lambda x: x['connection_rate']) if campaigns_data else None
        
        return jsonify({
            'client_id': client.id,
            'client_name': client.name,
            'period_days': days,
            'campaigns': campaigns_data,
            'summary': {
                'total_campaigns': len(campaigns_data),
                'active_campaigns': len([c for c in campaigns_data if c['status'] == 'active']),
                'total_leads': sum(c['total_leads'] for c in campaigns_data),
                'total_messages': sum(c['total_messages'] for c in campaigns_data),
                'total_replies': sum(c['total_replies'] for c in campaigns_data),
                'average_reply_rate': round(avg_reply_rate, 2),
                'average_connection_rate': round(avg_connection_rate, 2),
                'average_messages_per_lead': round(avg_messages_per_lead, 2),
                'average_replies_per_lead': round(avg_replies_per_lead, 2)
            },
            'best_performers': {
                'best_reply_rate': best_reply_rate,
                'best_connection_rate': best_connection_rate
            },
            'insights': {
                'reply_rate_variance': round(max(c['reply_rate'] for c in campaigns_data) - min(c['reply_rate'] for c in campaigns_data), 2) if campaigns_data else 0,
                'connection_rate_variance': round(max(c['connection_rate'] for c in campaigns_data) - min(c['connection_rate'] for c in campaigns_data), 2) if campaigns_data else 0
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in client comparative analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/comparative/campaigns', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def comparative_campaigns_analytics():
    """Get comparative analytics across all campaigns in the system."""
    try:
        days = request.args.get('days', default=30, type=int)
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get all campaigns
        campaigns = Campaign.query.all()
        campaigns_data = []
        
        for campaign in campaigns:
            # Get campaign events
            events = (
                db.session.query(Event)
                .join(Lead, Lead.id == Event.lead_id)
                .filter(Lead.campaign_id == campaign.id, Event.timestamp >= since)
                .all()
            )
            
            # Calculate metrics
            total_leads = len(campaign.leads)
            total_messages = sum(1 for e in events if e.event_type == "message_sent")
            total_replies = sum(1 for e in events if e.event_type == "message_received")
            total_invites = sum(1 for e in events if e.event_type == "connection_request_sent")
            total_connections = sum(1 for e in events if e.event_type in ["connection_accepted", "connection_accepted_historical"])
            
            reply_rate = (total_replies / total_messages * 100) if total_messages > 0 else 0
            connection_rate = (total_connections / total_invites * 100) if total_invites > 0 else 0
            
            # Get client info
            client_name = campaign.client.name if campaign.client else 'Unknown'
            
            campaigns_data.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'client_name': client_name,
                'status': campaign.status,
                'total_leads': total_leads,
                'total_messages': total_messages,
                'total_replies': total_replies,
                'total_invites': total_invites,
                'total_connections': total_connections,
                'reply_rate': round(reply_rate, 2),
                'connection_rate': round(connection_rate, 2),
                'messages_per_lead': round(total_messages / total_leads, 2) if total_leads > 0 else 0,
                'replies_per_lead': round(total_replies / total_leads, 2) if total_leads > 0 else 0
            })
        
        # Sort by reply rate
        campaigns_data.sort(key=lambda x: x['reply_rate'], reverse=True)
        
        # Calculate system-wide averages
        if campaigns_data:
            avg_reply_rate = sum(c['reply_rate'] for c in campaigns_data) / len(campaigns_data)
            avg_connection_rate = sum(c['connection_rate'] for c in campaigns_data) / len(campaigns_data)
            avg_messages_per_lead = sum(c['messages_per_lead'] for c in campaigns_data) / len(campaigns_data)
            avg_replies_per_lead = sum(c['replies_per_lead'] for c in campaigns_data) / len(campaigns_data)
        else:
            avg_reply_rate = avg_connection_rate = avg_messages_per_lead = avg_replies_per_lead = 0
        
        return jsonify({
            'period_days': days,
            'campaigns': campaigns_data,
            'system_summary': {
                'total_campaigns': len(campaigns_data),
                'active_campaigns': len([c for c in campaigns_data if c['status'] == 'active']),
                'total_leads': sum(c['total_leads'] for c in campaigns_data),
                'total_messages': sum(c['total_messages'] for c in campaigns_data),
                'total_replies': sum(c['total_replies'] for c in campaigns_data),
                'average_reply_rate': round(avg_reply_rate, 2),
                'average_connection_rate': round(avg_connection_rate, 2),
                'average_messages_per_lead': round(avg_messages_per_lead, 2),
                'average_replies_per_lead': round(avg_replies_per_lead, 2)
            },
            'top_performers': {
                'top_5_by_reply_rate': campaigns_data[:5],
                'top_5_by_connection_rate': sorted(campaigns_data, key=lambda x: x['connection_rate'], reverse=True)[:5]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in comparative campaigns analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# REAL-TIME ANALYTICS
# =============================================================================

@analytics_bp.route('/real-time/activity', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def real_time_activity():
    """Get real-time activity across all campaigns."""
    try:
        # Get recent activity (last 24 hours)
        since = datetime.utcnow() - timedelta(hours=24)
        
        recent_events = (
            db.session.query(Event)
            .join(Lead, Lead.id == Event.lead_id)
            .join(Campaign, Campaign.id == Lead.campaign_id)
            .filter(Event.timestamp >= since)
            .order_by(Event.timestamp.desc())
            .limit(50)
            .all()
        )
        
        # Group by campaign
        by_campaign = defaultdict(list)
        for event in recent_events:
            lead = Lead.query.get(event.lead_id)
            if lead and lead.campaign:
                by_campaign[lead.campaign.name].append({
                    'event_id': event.id,
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat() if event.timestamp else None,
                    'lead_name': f"{lead.first_name} {lead.last_name}" if lead else 'Unknown',
                    'campaign_name': lead.campaign.name
                })
        
        # Calculate activity summary
        activity_summary = {
            'total_events': len(recent_events),
            'invites_sent': sum(1 for e in recent_events if e.event_type == "connection_request_sent"),
            'messages_sent': sum(1 for e in recent_events if e.event_type == "message_sent"),
            'replies_received': sum(1 for e in recent_events if e.event_type == "message_received"),
            'connections_made': sum(1 for e in recent_events if e.event_type in ["connection_accepted", "connection_accepted_historical"])
        }
        
        return jsonify({
            'last_updated': datetime.utcnow().isoformat(),
            'period_hours': 24,
            'activity_summary': activity_summary,
            'recent_activity': dict(by_campaign),
            'latest_events': [
                {
                    'event_id': event.id,
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat() if event.timestamp else None,
                    'lead_name': f"{Lead.query.get(event.lead_id).first_name} {Lead.query.get(event.lead_id).last_name}" if Lead.query.get(event.lead_id) else 'Unknown',
                    'campaign_name': Lead.query.get(event.lead_id).campaign.name if Lead.query.get(event.lead_id) and Lead.query.get(event.lead_id).campaign else 'Unknown'
                }
                for event in recent_events[:10]  # Latest 10 events
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error in real-time activity: {str(e)}")
        return jsonify({'error': str(e)}), 500


