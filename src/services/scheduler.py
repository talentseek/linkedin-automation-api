import os
import logging
import random
import threading
import time
from datetime import datetime, timedelta, date
import pytz
from flask import current_app

from src.extensions import db
from src.models import Lead, LinkedInAccount, Campaign, Event
from src.services.sequence_engine import SequenceEngine
from src.models.rate_usage import RateUsage

logger = logging.getLogger(__name__)

class OutreachScheduler:
    """Simple background scheduler for managing LinkedIn outreach automation."""
    
    def __init__(self, app=None):
        self.app = app
        self.sequence_engine = None  # Initialize lazily
        self.running = False
        self.thread = None
        
        # Rate limiting configuration
        self.max_connections_per_day = 25
        self.max_messages_per_day = 100
        self.min_delay_between_actions = 300  # 5 minutes
        self.max_delay_between_actions = 1800  # 30 minutes
        self.working_hours_start = 9
        self.working_hours_end = 17
        
        # Daily counters - REMOVED: using persisted database instead
        self.last_reset_date = None
        # Nightly jobs control
        self.nightly_hour_utc = 1  # 01:00 UTC by default
        self._last_conversation_backfill_date = None
        self._last_rate_usage_backfill_date = None
        
        if app is not None:
            self.init_app(app)
    
    def _get_sequence_engine(self):
        """Get sequence engine instance (lazy initialization)."""
        if self.sequence_engine is None:
            self.sequence_engine = SequenceEngine()
        return self.sequence_engine
    
    def init_app(self, app):
        """Initialize the scheduler with the Flask app."""
        self.app = app
        
        # Load configuration from app config
        self.max_connections_per_day = app.config.get('MAX_CONNECTIONS_PER_DAY', 25)
        self.max_messages_per_day = app.config.get('MAX_MESSAGES_PER_DAY', 100)
        self.min_delay_between_actions = app.config.get('MIN_DELAY_BETWEEN_ACTIONS', 300)
        self.max_delay_between_actions = app.config.get('MAX_DELAY_BETWEEN_ACTIONS', 1800)
        self.working_hours_start = app.config.get('WORKING_HOURS_START', 9)
        self.working_hours_end = app.config.get('WORKING_HOURS_END', 17)
        
        logger.info(f"Scheduler initialized with simple thread-based approach")
    
    def start(self):
        """Start the background processing thread."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
        logger.info("Outreach scheduler started successfully")
    
    def stop(self):
        """Stop the background processing thread."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=5)
            logger.info("Outreach scheduler stopped")
    
    def _process_loop(self):
        """Main processing loop that runs continuously."""
        logger.info("Starting background processing loop")
        
        while self.running:
            try:
                # Process pending leads every 5 minutes
                self.process_pending_leads()
                
                # Reset daily counters at midnight
                self._check_and_reset_daily_counters()
                # Run nightly maintenance once per day after configured hour
                self._maybe_run_nightly_backfills()
                
                # Periodic connection detection check (every 2 hours)
                self._maybe_check_for_new_connections()
                
                # Sleep for 60 seconds before next iteration to reduce latency for new events
                time.sleep(60)  # 1 minute
                
            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Continue running even if there's an error
                time.sleep(60)  # Wait 1 minute before retrying
        
        logger.info("Background processing loop stopped")
    
    def _check_and_reset_daily_counters(self):
        """Check if it's time to reset daily counters."""
        try:
            current_date = datetime.utcnow().date()
            if self.last_reset_date != current_date:
                self.last_reset_date = current_date
                logger.info("Daily counter reset date updated")
        except Exception as e:
            logger.error(f"Error updating reset date: {str(e)}")

    def _maybe_check_for_new_connections(self):
        """Periodic check for new connections using Unipile relations API."""
        try:
            # Check every 2 hours (at 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
            utc_now = datetime.utcnow()
            if utc_now.hour % 2 != 0:
                return
            
            # Only run once per 2-hour window (check minute to avoid multiple runs)
            if utc_now.minute > 10:
                return
                
            logger.info("Starting periodic connection detection check")
            
            from src.models.linkedin_account import LinkedInAccount
            from src.services.unipile_client import UnipileClient
            
            # Get all connected LinkedIn accounts
            accounts = LinkedInAccount.query.filter_by(status='connected').all()
            
            for account in accounts:
                try:
                    self._check_account_relations(account)
                except Exception as e:
                    logger.error(f"Error checking relations for account {account.account_id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in periodic connection detection: {str(e)}")
    
    def _check_account_relations(self, linkedin_account):
        """Check relations for a specific LinkedIn account to detect new connections."""
        try:
            from src.services.unipile_client import UnipileClient
            from src.models import Lead, Event
            
            unipile = UnipileClient()
            
            # Also check the account ID that's being used in webhook events
            # This handles the case where webhooks monitor all accounts
            additional_account_ids = ['be9bc33c-9015-44d7-890f-b08e25fa0302']
            
            # Check both the database account and any additional accounts
            accounts_to_check = [linkedin_account.account_id] + additional_account_ids
            
            for account_id in accounts_to_check:
                try:
                    # Try relations API first
                    self._check_single_account_relations(account_id, unipile)
                except Exception as e:
                    logger.warning(f"Relations API failed for account {account_id}: {str(e)}")
                    # Fallback: check sent invitations for this account
                    try:
                        self._check_sent_invitations(account_id, unipile)
                    except Exception as e2:
                        logger.warning(f"Sent invitations API also failed for account {account_id}: {str(e2)}")
                    continue
                        
        except Exception as e:
            logger.error(f"Error checking relations for account {linkedin_account.account_id}: {str(e)}")
            db.session.rollback()
    
    def _check_single_account_relations(self, account_id, unipile):
        """Check relations for a single account ID."""
        try:
            from src.models import Lead, Event
            
            # Get recent relations (last 50 to avoid too many API calls)
            relations_response = unipile.get_relations(account_id, limit=50)
            if not relations_response or 'items' not in relations_response:
                logger.warning(f"No relations data for account {account_id}")
                return
            
            relations = relations_response['items']
            logger.info(f"Found {len(relations)} relations for account {account_id}")
            
            # Check each relation against our pending leads
            for relation in relations:
                # Unipile relations API uses 'member_id' field
                user_provider_id = relation.get('member_id') or relation.get('provider_id')
                if not user_provider_id:
                    continue
                
                # Find lead with this provider_id that has invite_sent status
                lead = Lead.query.filter_by(
                    provider_id=user_provider_id,
                    status='invite_sent'
                ).first()
                
                # If not found by provider_id, try fuzzy matching by name
                if not lead:
                    logger.info(f"Provider ID {user_provider_id} not found, trying fuzzy name matching")
                    # Get first and last name from relation
                    first_name = relation.get('first_name', '').strip()
                    last_name = relation.get('last_name', '').strip()
                    
                    if first_name and last_name:
                        # Try exact name match first
                        lead = Lead.query.filter_by(
                            first_name=first_name,
                            last_name=last_name,
                            status='invite_sent'
                        ).first()
                        
                        # If still not found, try case-insensitive matching
                        if not lead:
                            lead = Lead.query.filter(
                                Lead.first_name.ilike(first_name),
                                Lead.last_name.ilike(last_name),
                                Lead.status == 'invite_sent'
                            ).first()
                        
                        if lead:
                            logger.info(f"Found lead {lead.id} via fuzzy name matching: {first_name} {last_name}")
                        else:
                            logger.debug(f"No lead found for name: {first_name} {last_name}")
                
                if lead:
                    logger.info(f"New connection detected via relations API for lead {lead.id} from account {account_id}")
                    
                    # Update lead status to connected
                    lead.status = 'connected'
                    lead.connected_at = datetime.utcnow()
                    
                    # Try to get conversation ID
                    try:
                        conversation_id = unipile.find_conversation_with_provider(
                            account_id, 
                            user_provider_id
                        )
                        if conversation_id:
                            lead.conversation_id = conversation_id
                    except Exception as e:
                        logger.warning(f"Could not get conversation ID for lead {lead.id}: {str(e)}")
                    
                    # Create event record
                    event = Event(
                        event_type='connection_accepted',
                        lead_id=lead.id,
                        meta_json={
                            'account_id': account_id,
                            'user_provider_id': user_provider_id,
                            'detection_method': 'periodic_relations_check',
                            'relation_data': relation,
                            'conversation_id': lead.conversation_id
                        }
                    )
                    
                    db.session.add(event)
                    db.session.commit()
                    
                    logger.info(f"Successfully updated lead {lead.id} to connected status via relations check")
                    
                    # Trigger next step in sequence if automation is active
                    from src.models import Campaign
                    campaign = Campaign.query.get(lead.campaign_id)
                    if campaign and campaign.status == 'active':
                        # Find the LinkedIn account by account_id to get the database ID
                        linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
                        if linkedin_account:
                            # Schedule the next message step
                            self.schedule_lead_step(lead.id, linkedin_account.id)
                            logger.info(f"Scheduled next step for lead {lead.id} via relations check")
                        else:
                            logger.warning(f"LinkedIn account not found in database for account_id {account_id}, cannot schedule next step")
                        
        except Exception as e:
            logger.error(f"Error checking relations for account {account_id}: {str(e)}")
            db.session.rollback()
    
    def _check_sent_invitations(self, account_id, unipile):
        """Check sent invitations to detect which ones are no longer pending (accepted/rejected)."""
        try:
            from src.models import Lead, Event
            
            # Get sent invitations for this account
            invitations_response = unipile.get_sent_invitations(account_id)
            if not invitations_response or 'items' not in invitations_response:
                logger.warning(f"No sent invitations data for account {account_id}")
                return
            
            invitations = invitations_response['items']
            logger.info(f"Found {len(invitations)} sent invitations for account {account_id}")
            
            # Check each invitation against our pending leads
            for invitation in invitations:
                # Get the recipient's provider_id from the invitation
                recipient = invitation.get('recipient', {})
                user_provider_id = recipient.get('provider_id')
                
                if not user_provider_id:
                    continue
                
                # Check if invitation is no longer pending (accepted or rejected)
                invitation_status = invitation.get('status', 'pending')
                if invitation_status == 'pending':
                    continue  # Still pending, skip
                
                # Find lead with this provider_id that has invite_sent status
                lead = Lead.query.filter_by(
                    provider_id=user_provider_id,
                    status='invite_sent'
                ).first()
                
                # If not found by provider_id, try fuzzy matching by name
                if not lead:
                    logger.info(f"Provider ID {user_provider_id} not found in sent invitations, trying fuzzy name matching")
                    # Get first and last name from invitation recipient
                    recipient = invitation.get('recipient', {})
                    first_name = recipient.get('first_name', '').strip()
                    last_name = recipient.get('last_name', '').strip()
                    
                    if first_name and last_name:
                        # Try exact name match first
                        lead = Lead.query.filter_by(
                            first_name=first_name,
                            last_name=last_name,
                            status='invite_sent'
                        ).first()
                        
                        # If still not found, try case-insensitive matching
                        if not lead:
                            lead = Lead.query.filter(
                                Lead.first_name.ilike(first_name),
                                Lead.last_name.ilike(last_name),
                                Lead.status == 'invite_sent'
                            ).first()
                        
                        if lead:
                            logger.info(f"Found lead {lead.id} via fuzzy name matching in sent invitations: {first_name} {last_name}")
                        else:
                            logger.debug(f"No lead found for name in sent invitations: {first_name} {last_name}")
                
                if lead:
                    if invitation_status == 'accepted':
                        logger.info(f"Invitation accepted detected via sent invitations API for lead {lead.id} from account {account_id}")
                        
                        # Update lead status to connected
                        lead.status = 'connected'
                        lead.connected_at = datetime.utcnow()
                        
                        # Create event record
                        event = Event(
                            event_type='connection_accepted',
                            lead_id=lead.id,
                            meta_json={
                                'account_id': account_id,
                                'user_provider_id': user_provider_id,
                                'detection_method': 'sent_invitations_check',
                                'invitation_data': invitation,
                                'invitation_status': invitation_status
                            }
                        )
                        
                        db.session.add(event)
                        db.session.commit()
                        
                        logger.info(f"Successfully updated lead {lead.id} to connected status via sent invitations check")
                        
                        # Trigger next step in sequence if automation is active
                        from src.models import Campaign
                        campaign = Campaign.query.get(lead.campaign_id)
                        if campaign and campaign.status == 'active':
                            # Find the LinkedIn account by account_id to get the database ID
                            linkedin_account = LinkedInAccount.query.filter_by(account_id=account_id).first()
                            if linkedin_account:
                                # Schedule the next message step
                                self.schedule_lead_step(lead.id, linkedin_account.id)
                                logger.info(f"Scheduled next step for lead {lead.id} via sent invitations check")
                            else:
                                logger.warning(f"LinkedIn account not found in database for account_id {account_id}, cannot schedule next step")
                    
                    elif invitation_status == 'rejected':
                        logger.info(f"Invitation rejected detected for lead {lead.id} from account {account_id}")
                        # Could update lead status to 'rejected' if needed
                        
        except Exception as e:
            logger.error(f"Error checking sent invitations for account {account_id}: {str(e)}")
            db.session.rollback()

    def _maybe_run_nightly_backfills(self):
        try:
            utc_now = datetime.utcnow()
            if utc_now.hour < self.nightly_hour_utc:
                return
            today = utc_now.date()
            # Conversation ID backfill
            if self._last_conversation_backfill_date != today:
                self._run_conversation_id_backfill()
                self._last_conversation_backfill_date = today
            # Rate usage backfill
            if self._last_rate_usage_backfill_date != today:
                self._run_rate_usage_backfill()
                self._last_rate_usage_backfill_date = today
        except Exception as e:
            logger.error(f"Nightly backfills failed: {str(e)}")

    def _run_conversation_id_backfill(self):
        """Attempt to resolve conversation IDs for eligible leads."""
        try:
            with self.app.app_context():
                eligible_statuses = ['connected', 'messaged', 'responded']
                leads = (
                    Lead.query
                    .filter(Lead.status.in_(eligible_statuses))
                    .filter((Lead.conversation_id.is_(None)) | (Lead.conversation_id == ''))
                    .all()
                )
                if not leads:
                    logger.info("Conversation backfill: no eligible leads without conversation_id")
                    return
                # Choose a connected LinkedIn account per client when needed
                accounts_by_client = {}
                def get_account_for_lead(lead: Lead):
                    client_id = lead.campaign.client_id
                    if client_id in accounts_by_client:
                        return accounts_by_client[client_id]
                    acct = LinkedInAccount.query.filter_by(client_id=client_id, status='connected').first()
                    accounts_by_client[client_id] = acct
                    return acct
                unipile = self._get_sequence_engine()._get_unipile_client()
                updated = 0
                for lead in leads:
                    try:
                        acct = get_account_for_lead(lead)
                        if not acct:
                            continue
                        chat_id = unipile.find_conversation_with_provider(acct.account_id, lead.provider_id)
                        if chat_id:
                            lead.conversation_id = chat_id
                            updated += 1
                    except Exception as e:
                        logger.debug(f"Backfill chat id error for lead {lead.id}: {str(e)}")
                        continue
                db.session.commit()
                logger.info(f"Conversation backfill: updated {updated} of {len(leads)} leads")
        except Exception as e:
            logger.error(f"Conversation backfill failed: {str(e)}")

    def _run_rate_usage_backfill(self):
        """Backfill daily rate usage from events for yesterday (UTC)."""
        try:
            with self.app.app_context():
                from datetime import time as dtime
                # Yesterday UTC window
                utc_now = datetime.utcnow()
                yesterday = (utc_now.date() - timedelta(days=1))
                start = datetime.combine(yesterday, dtime.min)
                end = datetime.combine(yesterday + timedelta(days=1), dtime.min)
                # Fetch relevant events
                events = (
                    Event.query
                    .filter(Event.timestamp >= start, Event.timestamp < end)
                    .filter(Event.event_type.in_(['connection_request_sent', 'message_sent']))
                    .all()
                )
                if not events:
                    logger.info("Rate usage backfill: no events for yesterday")
                    return
                # Aggregate by linkedin_account_id
                from collections import defaultdict
                invites_by_acct = defaultdict(int)
                messages_by_acct = defaultdict(int)
                for ev in events:
                    meta = ev.meta_json or {}
                    acct_id = meta.get('linkedin_account_id')
                    if not acct_id:
                        continue
                    if ev.event_type == 'connection_request_sent':
                        invites_by_acct[acct_id] += 1
                    elif ev.event_type == 'message_sent':
                        messages_by_acct[acct_id] += 1
                # Upsert into RateUsage
                from src.models.rate_usage import RateUsage
                for acct_id in set(list(invites_by_acct.keys()) + list(messages_by_acct.keys())):
                    # Get or create row
                    row = (
                        db.session.query(RateUsage)
                        .filter(RateUsage.linkedin_account_id == acct_id, RateUsage.usage_date == yesterday)
                        .first()
                    )
                    if not row:
                        row = RateUsage(
                            id=str(db.func.uuid()),
                            linkedin_account_id=acct_id,
                            usage_date=yesterday,
                            invites_sent=0,
                            messages_sent=0,
                        )
                        db.session.add(row)
                    row.invites_sent = invites_by_acct.get(acct_id, 0)
                    row.messages_sent = messages_by_acct.get(acct_id, 0)
                db.session.commit()
                logger.info(f"Rate usage backfill: upserted {len(set(list(invites_by_acct.keys()) + list(messages_by_acct.keys())))} accounts for {yesterday}")
        except Exception as e:
            logger.error(f"Rate usage backfill failed: {str(e)}")
    
    # REMOVED: In-memory counter methods - using persisted database instead

    # ------------------------
    # Persisted, per-account usage gating
    # ------------------------
    def _get_today_usage_counts(self, provider_account_id: str):
        """Return (invites_today, messages_today) from persisted RateUsage for the given provider account id."""
        try:
            from src.models.rate_usage import RateUsage as RU
            today = date.today()
            row = (
                db.session.query(RU)
                .filter(RU.linkedin_account_id == provider_account_id, RU.usage_date == today)
                .first()
            )
            if not row:
                return 0, 0
            return (row.invites_sent or 0), (row.messages_sent or 0)
        except Exception as e:
            logger.warning(f"Failed to read RateUsage for {provider_account_id}: {str(e)}")
            return 0, 0

    def _can_send_invite_for_account(self, provider_account_id: str) -> bool:
        invites_today, _ = self._get_today_usage_counts(provider_account_id)
        return invites_today < int(self.max_connections_per_day)

    def _can_send_message_for_account(self, provider_account_id: str, is_first_level: bool) -> bool:
        _, messages_today = self._get_today_usage_counts(provider_account_id)
        limit = int(self.max_messages_per_day) * (2 if is_first_level else 1)
        return messages_today < limit
    
    def calculate_next_execution_time(self, timezone_str='Europe/London', delay_minutes=None):
        """Calculate the next execution time considering working hours and timezone."""
        if delay_minutes is None:
            delay_minutes = random.randint(
                self.min_delay_between_actions // 60,
                self.max_delay_between_actions // 60
            )
        
        try:
            # Get the timezone
            tz = pytz.timezone(timezone_str)
            
            # Calculate base time (now + delay)
            local_now = datetime.now(tz)
            local_next_time = local_now + timedelta(minutes=delay_minutes)
            
            # Check if within working hours
            if local_next_time.hour < self.working_hours_start:
                # Schedule for start of working hours today
                next_time = local_next_time.replace(
                    hour=self.working_hours_start,
                    minute=random.randint(0, 59),
                    second=0,
                    microsecond=0
                ).astimezone(pytz.UTC)
            elif local_next_time.hour >= self.working_hours_end:
                # Schedule for start of working hours next day
                next_day = local_next_time + timedelta(days=1)
                next_time = next_day.replace(
                    hour=self.working_hours_start,
                    minute=random.randint(0, 59),
                    second=0,
                    microsecond=0
                ).astimezone(pytz.UTC)
            else:
                # Within working hours, convert to UTC
                next_time = local_next_time.astimezone(pytz.UTC)
        except Exception as e:
            logger.warning(f"Error calculating working hours for timezone {timezone_str}: {str(e)}")
            # Fallback: ensure at least 5 minutes in the future
            next_time = datetime.now(pytz.UTC) + timedelta(minutes=max(5, delay_minutes))
        
        # Ensure the time is in the future
        utc_now = datetime.now(pytz.UTC)
        if next_time <= utc_now:
            next_time = utc_now + timedelta(minutes=5)
        
        return next_time
    
    def schedule_lead_step(self, lead_id, linkedin_account_id, delay_minutes=None):
        """Schedule a step for a specific lead (immediate execution for now)."""
        try:
            # For simplicity, execute immediately instead of scheduling
            logger.info(f"Executing step for lead {lead_id} immediately")
            self.execute_lead_step(lead_id, linkedin_account_id)
        except Exception as e:
            logger.error(f"Error scheduling/executing step for lead {lead_id}: {str(e)}")
    
    def execute_lead_step(self, lead_id, linkedin_account_id):
        """Execute a step for a specific lead with basic locking and idempotency safeguards."""
        try:
            with self.app.app_context():
                # Attempt to lock the lead row to prevent concurrent execution on the same lead
                try:
                    lead = (
                        db.session.query(Lead)
                        .filter(Lead.id == lead_id)
                        .with_for_update()
                        .one_or_none()
                    )
                except Exception:
                    # Fallback for databases that don't support row-level locking
                    lead = Lead.query.get(lead_id)
                if not lead:
                    logger.error(f"Lead {lead_id} not found")
                    return
                
                # Get the LinkedIn account
                linkedin_account = LinkedInAccount.query.get(linkedin_account_id)
                if not linkedin_account:
                    logger.error(f"LinkedIn account {linkedin_account_id} not found")
                    return
                
                # Check if campaign is active
                if lead.campaign.status != 'active':
                    logger.info(f"Campaign {lead.campaign.id} is not active, skipping lead {lead_id}")
                    return
                
                # Determine next step (after lock)
                next_step = self._get_sequence_engine().get_next_step_for_lead(lead)
                if not next_step:
                    logger.info(f"No next step for lead {lead_id}")
                    return
                
                # Check if step can be executed
                can_execute = self._get_sequence_engine().can_execute_step(lead, next_step)
                if not can_execute['can_execute']:
                    logger.info(f"Cannot execute step for lead {lead_id}: {can_execute['reason']}")
                    return
                
                # Idempotency: suppress duplicate sends within a short window
                try:
                    recent_window = datetime.utcnow() - timedelta(minutes=10)
                    if next_step.get('action_type') == 'message':
                        recent = (
                            db.session.query(Event)
                            .filter(Event.lead_id == lead.id, Event.event_type == 'message_sent', Event.timestamp >= recent_window)
                            .first()
                        )
                        if recent:
                            logger.warning(f"Idempotency: recent message_sent found for lead {lead_id}; skipping resend")
                            return
                    elif next_step.get('action_type') == 'connection_request':
                        recent = (
                            db.session.query(Event)
                            .filter(Event.lead_id == lead.id, Event.event_type == 'connection_request_sent', Event.timestamp >= recent_window)
                            .first()
                        )
                        if recent:
                            logger.warning(f"Idempotency: recent connection_request_sent found for lead {lead_id}; skipping resend")
                            return
                except Exception as _:
                    # Best-effort: do not block execution if idempotency check fails
                    pass
                
                # Execute the step
                result = self._get_sequence_engine().execute_step(lead, next_step, linkedin_account)
                
                if result['success']:
                    logger.info(f"Successfully executed step for lead {lead_id}")
                    
                    # Record the action
                    if next_step['action_type'] == 'connection_request':
                        # Persist usage to database
                        try:
                            RateUsage.increment(linkedin_account.account_id, invites=1)
                            logger.info(f"Recorded connection request for account {linkedin_account.account_id}")
                        except Exception as _:
                            logger.warning("Failed to persist invite usage; continuing")
                        # Update lead status to invite_sent (not connected yet)
                        lead.status = 'invite_sent'
                        db.session.commit()
                        logger.info(f"Updated lead {lead_id} status to invite_sent")
                    elif next_step['action_type'] == 'message':
                        is_first_level = bool(lead.meta_json and lead.meta_json.get('source') == 'first_level_connections')
                        # Persist usage to database
                        try:
                            RateUsage.increment(linkedin_account.account_id, messages=1)
                            logger.info(f"Recorded message for account {linkedin_account.account_id} (first_level={is_first_level})")
                        except Exception as _:
                            logger.warning("Failed to persist message usage; continuing")
                        # Update lead status to messaged
                        lead.status = 'messaged'
                        db.session.commit()
                        logger.info(f"Updated lead {lead_id} status to messaged")
                    
                    # Check if there are more steps in the sequence
                    next_next_step = self._get_sequence_engine().get_next_step_for_lead(lead)
                    if next_next_step:
                        logger.info(f"Lead {lead_id} has more steps in sequence - will be processed in next cycle")
                    else:
                        logger.info(f"Lead {lead_id} completed all steps in sequence")
                        lead.status = 'completed'
                        db.session.commit()
                else:
                    logger.error(f"Failed to execute step for lead {lead_id}: {result['error']}")
        
        except Exception as e:
            logger.error(f"Error executing step for lead {lead_id}: {str(e)}")
    
    def process_pending_leads(self):
        """Process all leads that are ready for outreach."""
        try:
            logger.info("Starting process_pending_leads job")
            
            with self.app.app_context():
                # Find leads that should be processed
                # Include newly connected leads explicitly and prioritize them
                leads = (
                    Lead.query
                    .filter(Lead.campaign.has(Campaign.status == 'active'))
                    .filter(Lead.status.in_(['pending_invite', 'connected']))
                    .order_by(Lead.status.desc(), Lead.created_at.asc())
                    .all()
                )
                
                logger.info(f"Found {len(leads)} leads to process")
                
                for lead in leads:
                    try:
                        logger.info(f"Processing lead {lead.id} with status {lead.status}")
                        
                        # Check if this lead is ready for processing
                        if not self._is_lead_ready_for_processing(lead):
                            logger.info(f"Lead {lead.id} not ready for processing")
                            continue
                        
                        logger.info(f"Lead {lead.id} is ready for processing")
                        
                        # Get next step
                        next_step = self._get_sequence_engine().get_next_step_for_lead(lead)
                        if not next_step:
                            logger.info(f"No next step for lead {lead.id}")
                            continue
                        
                        logger.info(f"Next step for lead {lead.id}: {next_step['action_type']}")
                        
                        # Check if step can be executed
                        can_execute = self._get_sequence_engine().can_execute_step(lead, next_step)
                        if not can_execute['can_execute']:
                            logger.info(f"Cannot execute step for lead {lead.id}: {can_execute['reason']}")
                            continue
                        
                        logger.info(f"Step can be executed for lead {lead.id}")
                        
                        # Find LinkedIn account for this client
                        linkedin_account = LinkedInAccount.query.filter_by(
                            client_id=lead.campaign.client_id,
                            status='connected'
                        ).first()
                        
                        if not linkedin_account:
                            logger.warning(f"No connected LinkedIn account found for client {lead.campaign.client_id}")
                            continue
                        
                        logger.info(f"Found LinkedIn account {linkedin_account.id} for lead {lead.id}")
                        
                        # Check rate limits before executing the step
                        if next_step['action_type'] == 'connection_request':
                            # Persisted per-account invite cap enforcement
                            if not self._can_send_invite_for_account(linkedin_account.account_id):
                                logger.warning(f"Persisted invite cap reached for account {linkedin_account.account_id}, skipping lead {lead.id}")
                                continue
                        elif next_step['action_type'] == 'message':
                            is_first_level = bool(lead.meta_json and lead.meta_json.get('source') == 'first_level_connections')
                            # Persisted per-account message cap enforcement (with 2x for first-level)
                            if not self._can_send_message_for_account(linkedin_account.account_id, is_first_level):
                                logger.warning(f"Persisted message cap reached for account {linkedin_account.account_id}, is_first_level={is_first_level}, skipping lead {lead.id}")
                                continue
                        
                        # Execute the step
                        logger.info(f"Executing step for lead {lead.id}")
                        self.execute_lead_step(lead.id, linkedin_account.id)
                        
                    except Exception as e:
                        logger.error(f"Error processing lead {lead.id}: {str(e)}")
                        continue
                
                logger.info("Completed process_pending_leads job")
        
        except Exception as e:
            logger.error(f"Critical error in process_pending_leads: {str(e)}")
            # Don't re-raise the exception to prevent killing the scheduler
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _is_lead_ready_for_processing(self, lead):
        """Check if a lead is ready for processing based on timing."""
        try:
            # Get the next step to determine timing
            next_step = self._get_sequence_engine().get_next_step_for_lead(lead)
            if not next_step:
                return False
            
            # Check if step can be executed
            can_execute = self._get_sequence_engine().can_execute_step(lead, next_step)
            if not can_execute['can_execute']:
                return False
            
            # For connection requests, always ready
            if next_step['action_type'] == 'connection_request':
                return True
            
            # For 1st-level connections, allow immediate first message
            try:
                is_first_level = bool(lead.meta_json and lead.meta_json.get('source') == 'first_level_connections')
            except Exception:
                is_first_level = False
            if next_step.get('action_type') == 'message' and lead.status == 'connected':
                # Allow immediate messaging for any newly connected lead (first-level or not)
                return True
            
            # For messages, check if enough time has passed since the last action
            # Use last_step_sent_at instead of created_at for proper timing
            
            # Get the step number (0 = connection request, 1 = first message, etc.)
            step_number = self._get_step_number(lead, next_step)
            
            # Calculate required delay based on step
            required_delay_minutes = self._get_required_delay_for_step(step_number)
            
            # Check if enough time has passed since the last step was sent
            # Use last_step_sent_at if available, otherwise fall back to created_at
            if lead.last_step_sent_at:
                time_since_last_step = datetime.utcnow() - lead.last_step_sent_at
                time_since_last_step_minutes = time_since_last_step.total_seconds() / 60
                
                if time_since_last_step_minutes >= required_delay_minutes:
                    logger.info(f"Lead {lead.id} ready for step {step_number} (required: {required_delay_minutes}min, elapsed: {time_since_last_step_minutes:.1f}min)")
                    return True
                else:
                    logger.debug(f"Lead {lead.id} not ready for step {step_number} (required: {required_delay_minutes}min, elapsed: {time_since_last_step_minutes:.1f}min)")
                    return False
            else:
                # Fallback: use created_at if last_step_sent_at is not available
                time_since_creation = datetime.utcnow() - lead.created_at
                time_since_creation_minutes = time_since_creation.total_seconds() / 60
                
                if time_since_creation_minutes >= required_delay_minutes:
                    logger.info(f"Lead {lead.id} ready for step {step_number} (fallback: required: {required_delay_minutes}min, elapsed: {time_since_creation_minutes:.1f}min)")
                    return True
                else:
                    logger.debug(f"Lead {lead.id} not ready for step {step_number} (fallback: required: {required_delay_minutes}min, elapsed: {time_since_creation_minutes:.1f}min)")
                    return False
                
        except Exception as e:
            logger.error(f"Error checking if lead {lead.id} is ready: {str(e)}")
            return False
    
    def _get_step_number(self, lead, next_step):
        """Get the step number for a lead."""
        try:
            # Use the next step's step_order to determine the message number
            # step_order 1 = connection request (no delay)
            # step_order 2 = first message (3 days delay)
            # step_order 3 = second message (6 days delay)
            # step_order 4 = third message (9 days delay)
            step_order = next_step.get('step_order', 1)
            
            # Convert step_order to message number (0-indexed)
            if step_order == 1:  # Connection request
                return 0
            elif step_order == 2:  # First message
                return 1
            elif step_order == 3:  # Second message
                return 2
            elif step_order == 4:  # Third message
                return 3
            else:
                return step_order - 1  # Fallback
        except Exception as e:
            logger.error(f"Error getting step number for lead {lead.id}: {str(e)}")
            return 0
    
    def _get_required_delay_for_step(self, step_number):
        """Get the required delay in minutes for a given step."""
        # Define delays based on realistic business timing
        # 3 working days = 3 * 24 * 60 = 4320 minutes
        delays = {
            0: 0,       # Connection request - immediate
            1: 4320,    # First message - 3 working days (3 * 24 * 60 = 4320 minutes)
            2: 8640,    # Second message - 6 working days (6 * 24 * 60 = 8640 minutes)
            3: 12960    # Third message - 9 working days (9 * 24 * 60 = 12960 minutes)
        }
        return delays.get(step_number, 0)

# Global scheduler instance - created lazily
_outreach_scheduler = None

def get_outreach_scheduler():
    """Get the global outreach scheduler instance (lazy initialization)."""
    global _outreach_scheduler
    if _outreach_scheduler is None:
        _outreach_scheduler = OutreachScheduler()
        logger.warning("Created new OutreachScheduler instance without app context - this may cause issues")
    return _outreach_scheduler

