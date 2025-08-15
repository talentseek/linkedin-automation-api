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


