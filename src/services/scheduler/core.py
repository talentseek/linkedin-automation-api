"""
Core scheduler functionality.

This module contains the main scheduler class and core functionality:
- OutreachScheduler class
- Thread management
- Main processing loop
- Scheduler lifecycle management
"""

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

# Import methods from separate modules
from .rate_limiting import (
    _get_today_usage_counts,
    _can_send_invite_for_account,
    _can_send_message_for_account,
    _increment_usage,
    _reset_daily_counters
)
from .lead_processor import (
    _is_lead_ready_for_processing,
    _process_single_lead,
    _get_step_number,
    _get_required_delay_for_step
)
from .connection_checker import (
    _check_single_account_relations,
    _process_relation,
    _check_sent_invitations,
    _process_sent_invitation
)
from .nightly_jobs import (
    _maybe_run_nightly_backfills,
    _run_conversation_id_backfill,
    _run_rate_usage_backfill
)

logger = logging.getLogger(__name__)

# Global scheduler instance
_outreach_scheduler = None

def get_outreach_scheduler():
    """Get the global scheduler instance."""
    global _outreach_scheduler
    if _outreach_scheduler is None:
        _outreach_scheduler = OutreachScheduler()
    return _outreach_scheduler

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
    
    # Add the missing methods as class methods
    def _get_today_usage_counts(self, provider_account_id: str) -> dict:
        """Get today's usage counts for a LinkedIn account."""
        return _get_today_usage_counts(provider_account_id)
    
    def _can_send_invite_for_account(self, provider_account_id: str) -> bool:
        """Check if we can send an invite for a LinkedIn account."""
        return _can_send_invite_for_account(provider_account_id)
    
    def _can_send_message_for_account(self, provider_account_id: str) -> bool:
        """Check if we can send a message for a LinkedIn account."""
        return _can_send_message_for_account(provider_account_id)
    
    def _increment_usage(self, provider_account_id: str, action_type: str):
        """Increment usage for a LinkedIn account."""
        return _increment_usage(provider_account_id, action_type)
    
    def _reset_daily_counters(self):
        """Reset daily counters."""
        return _reset_daily_counters()
    
    def _is_lead_ready_for_processing(self, lead: Lead) -> bool:
        """Check if a lead is ready for processing."""
        return _is_lead_ready_for_processing(self, lead)
    
    def _process_single_lead(self, lead: Lead):
        """Process a single lead."""
        return _process_single_lead(self, lead)
    
    def _get_step_number(self, lead: Lead) -> int:
        """Get the current step number for a lead."""
        return _get_step_number(lead)
    
    def _get_required_delay_for_step(self, step_number: int) -> int:
        """Get the required delay for a step."""
        return _get_required_delay_for_step(self, step_number)
    
    def _check_single_account_relations(self, linkedin_account: LinkedInAccount):
        """Check relations for a single LinkedIn account."""
        return _check_single_account_relations(self, linkedin_account)
    
    def _process_relation(self, relation_data: dict, linkedin_account: LinkedInAccount):
        """Process a relation."""
        return _process_relation(self, relation_data, linkedin_account)
    
    def _check_sent_invitations(self, linkedin_account: LinkedInAccount):
        """Check sent invitations for a LinkedIn account."""
        return _check_sent_invitations(self, linkedin_account)
    
    def _process_sent_invitation(self, invitation_data: dict, linkedin_account: LinkedInAccount):
        """Process a sent invitation."""
        return _process_sent_invitation(self, invitation_data, linkedin_account)
    
    def _maybe_run_nightly_backfills(self):
        """Maybe run nightly backfills."""
        return _maybe_run_nightly_backfills(self)
    
    def _run_conversation_id_backfill(self):
        """Run conversation ID backfill."""
        return _run_conversation_id_backfill()
    
    def _run_rate_usage_backfill(self):
        """Run rate usage backfill."""
        return _run_rate_usage_backfill()
    
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
        if not self.running:
            logger.info("Scheduler is already stopped")
            return
        
        logger.info("Stopping scheduler...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            # Wait for thread to finish with a longer timeout
            logger.info("Waiting for scheduler thread to terminate...")
            self.thread.join(timeout=30)  # Increased timeout to 30 seconds
            
            if self.thread.is_alive():
                logger.warning("Scheduler thread did not terminate gracefully within 30 seconds")
                # Force thread termination if needed
                import ctypes
                try:
                    thread_id = self.thread.ident
                    if thread_id:
                        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(SystemExit))
                        if res > 1:
                            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
                            logger.error("Failed to terminate scheduler thread")
                        else:
                            logger.info("Forced scheduler thread termination")
                except Exception as e:
                    logger.error(f"Error forcing thread termination: {str(e)}")
        
        logger.info("Scheduler stopped")
    
    def _process_loop(self):
        """Main processing loop for the scheduler."""
        logger.info("Starting scheduler processing loop")
        
        while self.running:
            try:
                # Check if it's weekend (skip processing)
                if self._is_weekend():
                    logger.info("Weekend detected - skipping processing")
                    time.sleep(3600)  # Sleep for 1 hour
                    continue
                
                # Check and reset daily counters
                self._check_and_reset_daily_counters()
                
                # Maybe check for new connections
                self._maybe_check_for_new_connections()
                
                # Maybe run nightly backfills
                self._maybe_run_nightly_backfills()
                
                # Process leads
                self._process_leads()
                
                # Random delay between iterations
                delay = random.randint(60, 300)  # 1-5 minutes
                logger.info(f"Processing complete, sleeping for {delay} seconds")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error in scheduler processing loop: {str(e)}")
                time.sleep(60)  # Sleep for 1 minute on error
        
        logger.info("Scheduler processing loop ended")
    
    def _check_and_reset_daily_counters(self):
        """Check and reset daily counters if needed."""
        try:
            today = date.today()
            if self.last_reset_date != today:
                logger.info("Resetting daily counters")
                self.last_reset_date = today
        except Exception as e:
            logger.error(f"Error resetting daily counters: {str(e)}")
    
    def _maybe_check_for_new_connections(self):
        """Periodically check for new connections."""
        try:
            # Only check every 30 minutes
            current_time = datetime.utcnow()
            if hasattr(self, '_last_connection_check') and self._last_connection_check:
                time_since_last_check = (current_time - self._last_connection_check).total_seconds()
                if time_since_last_check < 1800:  # 30 minutes
                    return
            
            self._last_connection_check = current_time
            
            logger.info("Starting periodic connection detection check")
            
            with self.app.app_context():
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
            logger.error(f"Error in connection check: {str(e)}")
    
    def _check_account_relations(self, linkedin_account):
        """Check relations for a specific LinkedIn account."""
        try:
            from src.services.unipile_client import UnipileClient
            
            unipile = UnipileClient()
            self._check_single_account_relations(linkedin_account.account_id, unipile)
            
        except Exception as e:
            logger.error(f"Error checking relations for account {linkedin_account.account_id}: {str(e)}")
            # Note: db.session.rollback() removed as it's not needed without app context
    
    def _process_leads(self):
        """Process leads that are ready for the next step."""
        try:
            with self.app.app_context():
                # Get leads that are ready for processing
                leads = Lead.query.filter(
                    Lead.status.in_(['pending_invite', 'connected', 'messaged'])
                ).all()
                
                for lead in leads:
                    try:
                        # CRITICAL FIX: Validate lead before processing
                        if not lead or not hasattr(lead, 'id'):
                            logger.error("Invalid lead object in scheduler - skipping")
                            continue
                        
                        # Refresh lead data to ensure we have the correct information
                        try:
                            db.session.refresh(lead)
                            logger.info(f"Processing lead: {lead.first_name} {lead.last_name} (ID: {lead.id})")
                        except Exception as refresh_error:
                            logger.error(f"Failed to refresh lead {lead.id}: {str(refresh_error)}")
                            continue
                        
                        if self._is_lead_ready_for_processing(lead):
                            self._process_single_lead(lead)
                    except Exception as e:
                        logger.error(f"Error processing lead {lead.id}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error in lead processing: {str(e)}")
    
    def _is_weekend(self):
        """Check if current time is weekend."""
        current_time = datetime.utcnow()
        return current_time.weekday() >= 5  # Saturday = 5, Sunday = 6
    
    def schedule_lead_step(self, lead_id, linkedin_account_id):
        """Schedule a lead for the next step."""
        try:
            with self.app.app_context():
                lead = Lead.query.get(lead_id)
                if lead:
                    logger.info(f"Scheduling next step for lead {lead_id}")
                    # The lead will be processed in the next iteration
        except Exception as e:
            logger.error(f"Error scheduling lead step: {str(e)}")
