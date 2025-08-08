import os
import logging
import random
import threading
import time
from datetime import datetime, timedelta
import pytz
from flask import current_app

from src.extensions import db
from src.models import Lead, LinkedInAccount, Campaign
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
        
        # Daily counters
        self.daily_connections = 0
        self.daily_messages = 0
        self.last_reset_date = None
        
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
                
                # Sleep for 5 minutes before next iteration
                time.sleep(300)  # 5 minutes
                
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
                self.daily_connections = 0
                self.daily_messages = 0
                self.last_reset_date = current_date
                logger.info("Daily counters reset")
        except Exception as e:
            logger.error(f"Error resetting daily counters: {str(e)}")
    
    def can_send_connection(self):
        """Check if we can send a connection request."""
        return self.daily_connections < self.max_connections_per_day
    
    def can_send_message(self):
        """Check if we can send a message."""
        return self.daily_messages < self.max_messages_per_day
    
    def record_connection_sent(self):
        """Record that a connection request was sent."""
        self.daily_connections += 1
        logger.info(f"Connection sent. Daily count: {self.daily_connections}/{self.max_connections_per_day}")
    
    def record_message_sent(self):
        """Record that a message was sent."""
        self.daily_messages += 1
        logger.info(f"Message sent. Daily count: {self.daily_messages}/{self.max_messages_per_day}")
    
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
        """Execute a step for a specific lead."""
        try:
            with self.app.app_context():
                # Get the lead
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
                
                # Get next step
                next_step = self._get_sequence_engine().get_next_step_for_lead(lead)
                if not next_step:
                    logger.info(f"No next step for lead {lead_id}")
                    return
                
                # Check if step can be executed
                can_execute = self._get_sequence_engine().can_execute_step(lead, next_step)
                if not can_execute['can_execute']:
                    logger.info(f"Cannot execute step for lead {lead_id}: {can_execute['reason']}")
                    return
                
                # Execute the step
                result = self._get_sequence_engine().execute_step(lead, next_step, linkedin_account)
                
                if result['success']:
                    logger.info(f"Successfully executed step for lead {lead_id}")
                    
                    # Record the action
                    if next_step['action_type'] == 'connection_request':
                        if self.can_send_connection():
                            self.record_connection_sent()
                            # Persist usage
                            try:
                                RateUsage.increment(linkedin_account.account_id, invites=1)
                            except Exception as _:
                                logger.warning("Failed to persist invite usage; continuing")
                            # Update lead status to connected
                            lead.status = 'connected'
                            db.session.commit()
                            logger.info(f"Updated lead {lead_id} status to connected")
                        else:
                            logger.warning(f"Daily connection limit reached for lead {lead_id}")
                    elif next_step['action_type'] == 'message':
                        if self.can_send_message():
                            self.record_message_sent()
                            # Persist usage
                            try:
                                RateUsage.increment(linkedin_account.account_id, messages=1)
                            except Exception as _:
                                logger.warning("Failed to persist message usage; continuing")
                            # Update lead status to messaged
                            lead.status = 'messaged'
                            db.session.commit()
                            logger.info(f"Updated lead {lead_id} status to messaged")
                        else:
                            logger.warning(f"Daily message limit reached for lead {lead_id}")
                    
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
                leads = Lead.query.filter(
                    Lead.status.in_(['pending_invite', 'connected']),
                    Lead.campaign.has(Campaign.status == 'active')
                ).all()
                
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
                            if not self.can_send_connection():
                                logger.warning(f"Daily connection limit reached ({self.daily_connections}/{self.max_connections_per_day}), skipping lead {lead.id}")
                                continue
                        elif next_step['action_type'] == 'message':
                            if not self.can_send_message():
                                logger.warning(f"Daily message limit reached ({self.daily_messages}/{self.max_messages_per_day}), skipping lead {lead.id}")
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

