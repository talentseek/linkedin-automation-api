import logging
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Campaign, LinkedInAccount
from src.services.scheduler import get_outreach_scheduler
from datetime import datetime
from src.models import Lead

logger = logging.getLogger(__name__)

automation_bp = Blueprint('automation', __name__)


@automation_bp.route('/campaigns/<campaign_id>/start', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def start_campaign_automation(campaign_id):
    """Start automated outreach for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Validate campaign has a sequence
        if not campaign.sequence_json:
            return jsonify({'error': 'Campaign must have a sequence defined before starting'}), 400
        
        # Validate client has connected LinkedIn accounts
        linkedin_accounts = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).all()
        
        if not linkedin_accounts:
            return jsonify({'error': 'Client must have at least one connected LinkedIn account'}), 400
        
        # Start the campaign
        outreach_scheduler = get_outreach_scheduler()
        outreach_scheduler.start_campaign(campaign_id)
        
        return jsonify({
            'message': 'Campaign automation started successfully',
            'campaign': campaign.to_dict(),
            'connected_accounts': len(linkedin_accounts)
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting campaign automation: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/campaigns/<campaign_id>/pause', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def pause_campaign_automation(campaign_id):
    """Pause automated outreach for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Set campaign status to paused
        campaign.status = 'paused'
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign automation paused successfully',
            'campaign': campaign.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error pausing campaign automation: {str(e)}")
        return jsonify({'error': str(e)}), 500





@automation_bp.route('/campaigns/<campaign_id>/status', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_campaign_automation_status(campaign_id):
    """Get the automation status for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Count leads by status
        lead_stats = {}
        for lead in campaign.leads:
            status = lead.status
            lead_stats[status] = lead_stats.get(status, 0) + 1
        
        # Get scheduled jobs for this campaign
        scheduled_jobs = []
        outreach_scheduler = get_outreach_scheduler()
        
        # For thread-based scheduler, we don't have individual scheduled jobs
        # but we can show if the scheduler is running
        if outreach_scheduler.running:
            scheduled_jobs = [{
                'job_id': 'background_processor',
                'lead_id': 'all_pending_leads',
                'next_run_time': 'Continuous processing every 5 minutes'
            }]
        
        return jsonify({
            'campaign_id': campaign_id,
            'status': campaign.status,
            'lead_statistics': lead_stats,
            'total_leads': len(campaign.leads),
            'scheduled_jobs': len(scheduled_jobs),
            'upcoming_jobs': scheduled_jobs[:10]  # Show next 10 jobs
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign automation status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/rate-limits/<linkedin_account_id>', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_rate_limits(linkedin_account_id):
    """Get current rate limit status for a LinkedIn account."""
    try:
        linkedin_account = LinkedInAccount.query.get(linkedin_account_id)
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found'}), 404
        
        # Compute usage for today from RateUsage (fallback to events if missing)
        from datetime import date, datetime, timedelta
        from src.models.rate_usage import RateUsage
        from src.models import Event
        
        today = date.today()
        invites_today = 0
        messages_today = 0
        row = (
            db.session.query(RateUsage)
            .filter(RateUsage.linkedin_account_id == linkedin_account.account_id, RateUsage.usage_date == today)
            .first()
        )
        if row:
            invites_today = row.invites_sent or 0
            messages_today = row.messages_sent or 0
        else:
            # Fallback: aggregate events since midnight UTC
            start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            events = (
                db.session.query(Event)
                .filter(Event.timestamp >= start)
                .all()
            )
            for ev in events:
                meta = ev.meta_json or {}
                if meta.get('linkedin_account_id') == linkedin_account.id:
                    if ev.event_type == 'connection_request_sent':
                        invites_today += 1
                    elif ev.event_type == 'message_sent':
                        messages_today += 1
        
        # Limits from config
        invites_limit = int(current_app.config.get('MAX_CONNECTIONS_PER_DAY', 25))
        messages_limit = int(current_app.config.get('MAX_MESSAGES_PER_DAY', 100))
        first_level_messages_limit = messages_limit * 2
        
        return jsonify({
            'linkedin_account_id': linkedin_account.id,
            'account_id': linkedin_account.account_id,
            'daily_limits': {
                'invites': {
                    'current': invites_today,
                    'limit': invites_limit,
                    'remaining': max(0, invites_limit - invites_today)
                },
                'messages': {
                    'current': messages_today,
                    'limit': messages_limit,
                    'remaining': max(0, messages_limit - messages_today)
                },
                'first_level_messages': {
                    'current': messages_today,
                    'limit': first_level_messages_limit,
                    'remaining': max(0, first_level_messages_limit - messages_today)
                }
            },
            'can_send': {
                'invite': invites_today < invites_limit,
                'message_normal': messages_today < messages_limit,
                'message_first_level': messages_today < first_level_messages_limit
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting rate limits: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/status', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_scheduler_status():
    """Get the current status of the outreach scheduler."""
    try:
        outreach_scheduler = get_outreach_scheduler()
        
        # Use the new is_running() method for accurate status
        is_running = outreach_scheduler.is_running()
        
        # Get thread status for debugging
        thread_alive = False
        if outreach_scheduler and hasattr(outreach_scheduler, 'thread') and outreach_scheduler.thread is not None:
            try:
                thread_alive = outreach_scheduler.thread.is_alive()
            except Exception:
                thread_alive = False
        
        return jsonify({
            'status': 'running' if is_running else 'stopped',
            'running': is_running,
            'thread_alive': thread_alive,
            'state_consistent': is_running == thread_alive
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/start', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def start_scheduler():
    """Start the background scheduler."""
    try:
        logger.info("Attempting to start scheduler...")
        outreach_scheduler = get_outreach_scheduler()
        
        logger.info(f"Scheduler instance: {outreach_scheduler}")
        logger.info(f"Scheduler running state: {outreach_scheduler.running}")
        
        if not outreach_scheduler.running:
            logger.info("Starting scheduler...")
            outreach_scheduler.start()
            logger.info("Scheduler start() completed")
            return jsonify({'message': 'Scheduler started successfully'}), 200
        else:
            logger.info("Scheduler is already running")
            return jsonify({'message': 'Scheduler is already running'}), 200
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/stop', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def stop_scheduler():
    """Stop the background scheduler."""
    try:
        outreach_scheduler = get_outreach_scheduler()
        
        if outreach_scheduler.running:
            outreach_scheduler.stop()
            return jsonify({'message': 'Scheduler stopped successfully'}), 200
        else:
            return jsonify({'message': 'Scheduler is not running'}), 200
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/scheduler/weekend-status', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_weekend_status():
    """Get the current weekend status and scheduler behavior."""
    try:
        outreach_scheduler = get_outreach_scheduler()
        
        # Check if it's currently weekend
        is_weekend = outreach_scheduler._is_weekend()
        
        # Get current UTC time for reference
        from datetime import datetime
        utc_now = datetime.utcnow()
        
        return jsonify({
            'is_weekend': is_weekend,
            'current_time_utc': utc_now.isoformat(),
            'weekday': utc_now.weekday(),  # 0=Monday, 6=Sunday
            'weekday_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][utc_now.weekday()],
            'scheduler_behavior': 'weekend_mode' if is_weekend else 'normal_mode',
            'description': 'Outbound operations paused, webhooks active' if is_weekend else 'Normal operations'
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting weekend status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/leads/<lead_id>/schedule-step', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def schedule_lead_step(lead_id):
    """Schedule a step for a specific lead."""
    try:
        data = request.get_json()
        if not data or 'linkedin_account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        linkedin_account_id = data['linkedin_account_id']
        delay_minutes = data.get('delay_minutes', 1)
        
        outreach_scheduler = get_outreach_scheduler()
        outreach_scheduler.schedule_lead_step(lead_id, linkedin_account_id, delay_minutes)
        
        return jsonify({
            'message': 'Lead step scheduled successfully',
            'lead_id': lead_id,
            'linkedin_account_id': linkedin_account_id,
            'delay_minutes': delay_minutes
        }), 200
        
    except Exception as e:
        logger.error(f"Error scheduling lead step: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/process-leads', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_process_leads():
    """Test endpoint to manually trigger lead processing."""
    try:
        logger.info("Manual test: Triggering process_pending_leads")
        outreach_scheduler = get_outreach_scheduler()
        
        # Manually call the process_pending_leads function
        outreach_scheduler.process_pending_leads()
        
        return jsonify({
            'message': 'Lead processing completed successfully',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test_process_leads: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/sequence-debug', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def debug_sequence_engine():
    """Debug endpoint to test sequence engine logic."""
    try:
        # Get a lead from the campaign
        campaign_id = "263b189e-c56a-441d-a696-a422de28621c"
        lead = Lead.query.filter_by(campaign_id=campaign_id).first()
        
        if not lead:
            return jsonify({'error': 'No leads found'}), 404
        
        # Get sequence engine
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        
        # Test get_next_step_for_lead
        next_step = sequence_engine.get_next_step_for_lead(lead)
        
        # Test can_execute_step
        can_execute = None
        if next_step:
            can_execute = sequence_engine.can_execute_step(lead, next_step)
        
        return jsonify({
            'lead_id': lead.id,
            'lead_status': lead.status,
            'lead_current_step': lead.current_step,
            'campaign_sequence': lead.campaign.sequence,
            'next_step': next_step,
            'can_execute': can_execute
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/ready-check', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def debug_lead_ready_check():
    """Debug endpoint to test _is_lead_ready_for_processing method."""
    try:
        # Get a lead from the campaign
        campaign_id = "263b189e-c56a-441d-a696-a422de28621c"
        lead = Lead.query.filter_by(campaign_id=campaign_id).first()
        
        if not lead:
            return jsonify({'error': 'No leads found'}), 404
        
        # Get scheduler
        outreach_scheduler = get_outreach_scheduler()
        
        # Test _is_lead_ready_for_processing
        is_ready = outreach_scheduler._is_lead_ready_for_processing(lead)
        
        # Get next step for comparison
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        next_step = sequence_engine.get_next_step_for_lead(lead)
        can_execute = None
        if next_step:
            can_execute = sequence_engine.can_execute_step(lead, next_step)
        
        return jsonify({
            'lead_id': lead.id,
            'lead_status': lead.status,
            'lead_current_step': lead.current_step,
            'lead_created_at': lead.created_at.isoformat(),
            'is_ready_for_processing': is_ready,
            'next_step': next_step,
            'can_execute': can_execute
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/reset-leads', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def reset_campaign_leads():
    """Reset all leads in the campaign back to pending_invite status for testing."""
    try:
        campaign_id = "263b189e-c56a-441d-a696-a422de28621c"
        
        # Reset all leads in the campaign
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        
        for lead in leads:
            lead.status = 'pending_invite'
            lead.current_step = 0
            lead.last_step_sent_at = None
        
        db.session.commit()
        
        return jsonify({
            'message': f'Reset {len(leads)} leads back to pending_invite status',
            'leads_reset': len(leads)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@automation_bp.route('/test/format-message', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_format_message():
    """Test message formatting for a specific lead."""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        # Get the lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get the sequence engine
        sequence_engine = get_outreach_scheduler()._get_sequence_engine()
        
        # Test message formatting
        test_message = data.get('test_message', "Hi {first_name}, I work with manufacturing leaders like you to cut costly errors in order processing. Thought it might make sense to connect.")
        formatted_message = sequence_engine._format_message(test_message, lead)
        
        return jsonify({
            'lead_id': lead_id,
            'lead_name': f"{lead.first_name} {lead.last_name}",
            'lead_company': lead.company_name,
            'original_message': test_message,
            'formatted_message': formatted_message
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/notifications/settings', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_notification_settings():
    """Get current notification settings."""
    try:
        from src.services.notifications import get_notification_service
        
        notification_service = get_notification_service()
        
        return jsonify({
            'enabled': notification_service.enabled,
            'from_email': notification_service.from_email,
            'to_emails': notification_service.to_emails,
            'resend_configured': bool(notification_service.resend_api_key)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/notifications/test', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_notification():
    """Send a test notification to verify configuration."""
    try:
        from src.services.notifications import get_notification_service
        
        notification_service = get_notification_service()
        
        if not notification_service.enabled:
            return jsonify({'error': 'Notifications are disabled'}), 400
        
        # Send a test notification
        success = notification_service.send_error_notification(
            error_type="Test Notification",
            error_message="This is a test notification to verify your email configuration is working correctly.",
            context={
                'test_time': datetime.utcnow().isoformat(),
                'system': 'LinkedIn Automation API'
            }
        )
        
        if success:
            return jsonify({'message': 'Test notification sent successfully'}), 200
        else:
            return jsonify({'error': 'Failed to send test notification'}), 500
            
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/notifications/simple-test', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def simple_test_notification():
    """Simple test notification to verify Resend is working."""
    try:
        import resend
        import os
        
        # Get API key from environment
        api_key = os.environ.get('RESEND_API_KEY')
        if not api_key:
            return jsonify({'error': 'No Resend API key found'}), 400
        
        resend.api_key = api_key
        
        # Send a simple test email
        response = resend.Emails.send({
            "from": "notifications@send.notifications.costperdemo.com",
            "to": "michael@costperdemo.com",
            "subject": "🧪 Test Notification - LinkedIn Automation API",
            "html": """
            <h2>Test Notification</h2>
            <p>This is a simple test to verify that Resend is working correctly.</p>
            <p><strong>Time:</strong> """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
            <p>If you receive this email, the notification system is working!</p>
            """
        })
        
        return jsonify({
            'message': 'Simple test notification sent successfully',
            'email_id': response.get('id'),
            'response': response
        }), 200
        
    except Exception as e:
        logger.error(f"Error in simple test notification: {str(e)}")
        return jsonify({'error': str(e)}), 500

