"""
Nightly maintenance and backfill jobs.

This module contains functionality for:
- Nightly job scheduling
- Conversation ID backfill
- Rate usage backfill
- Maintenance tasks
"""

import logging
from datetime import datetime, date, timedelta
from src.models import db, Lead, LinkedInAccount, Event
from src.services.unipile_client import UnipileClient

logger = logging.getLogger(__name__)


def _maybe_run_nightly_backfills(self):
    """Run nightly backfill jobs if it's the right time."""
    try:
        current_time = datetime.utcnow()
        
        # Only run once per day at the specified hour
        if current_time.hour != self.nightly_hour_utc:
            return
        
        # Check if we've already run today
        today = date.today()
        if self._last_conversation_backfill_date == today:
            return
        
        logger.info("Running nightly backfill jobs")
        
        # Run conversation ID backfill
        self._run_conversation_id_backfill()
        
        # Run rate usage backfill
        self._run_rate_usage_backfill()
        
        # Update last run dates
        self._last_conversation_backfill_date = today
        self._last_rate_usage_backfill_date = today
        
        logger.info("Nightly backfill jobs completed")
        
    except Exception as e:
        logger.error(f"Error running nightly backfills: {str(e)}")


def _run_conversation_id_backfill(self):
    """Backfill conversation IDs for leads that don't have them."""
    try:
        logger.info("Starting conversation ID backfill")
        
        # Get leads without conversation IDs
        leads = Lead.query.filter(
            Lead.conversation_id.is_(None),
            Lead.status.in_(['connected', 'messaged', 'responded'])
        ).all()
        
        if not leads:
            logger.info("No leads need conversation ID backfill")
            return
        
        logger.info(f"Found {len(leads)} leads needing conversation ID backfill")
        
        # Group leads by campaign to get LinkedIn accounts
        campaigns = {}
        for lead in leads:
            if lead.campaign_id not in campaigns:
                campaigns[lead.campaign_id] = []
            campaigns[lead.campaign_id].append(lead)
        
        # Process each campaign
        for campaign_id, campaign_leads in campaigns.items():
            try:
                from src.models import Campaign
                campaign = Campaign.query.get(campaign_id)
                if not campaign:
                    continue
                
                # Get LinkedIn account for this campaign
                linkedin_account = LinkedInAccount.query.filter_by(
                    client_id=campaign.client_id,
                    status='connected'
                ).first()
                
                if not linkedin_account:
                    continue
                
                # Use Unipile API to get conversation IDs
                unipile = UnipileClient()
                
                for lead in campaign_leads:
                    try:
                        if not lead.public_identifier:
                            continue
                        
                        # Get conversation ID from Unipile
                        conversation_id = unipile.get_conversation_id(
                            account_id=linkedin_account.account_id,
                            public_identifier=lead.public_identifier
                        )
                        
                        if conversation_id:
                            lead.conversation_id = conversation_id
                            logger.info(f"Backfilled conversation ID for lead {lead.id}")
                        
                    except Exception as e:
                        logger.error(f"Error backfilling conversation ID for lead {lead.id}: {str(e)}")
                        continue
                
                # Commit changes for this campaign
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Error processing campaign {campaign_id} for conversation ID backfill: {str(e)}")
                db.session.rollback()
                continue
        
        logger.info("Conversation ID backfill completed")
        
    except Exception as e:
        logger.error(f"Error in conversation ID backfill: {str(e)}")
        db.session.rollback()


def _run_rate_usage_backfill(self):
    """Backfill rate usage data for missing days."""
    try:
        logger.info("Starting rate usage backfill")
        
        from src.models.rate_usage import RateUsage
        
        # Get all LinkedIn accounts
        accounts = LinkedInAccount.query.filter_by(status='connected').all()
        
        for account in accounts:
            try:
                # Check last 7 days for missing rate usage records
                today = date.today()
                for i in range(7):
                    check_date = today - timedelta(days=i)
                    
                    # Check if record exists
                    existing = RateUsage.query.filter_by(
                        provider_account_id=account.account_id,
                        date=check_date
                    ).first()
                    
                    if not existing:
                        # Create missing record
                        usage = RateUsage(
                            provider_account_id=account.account_id,
                            date=check_date,
                            connections_sent=0,
                            messages_sent=0
                        )
                        db.session.add(usage)
                        logger.info(f"Created missing rate usage record for {account.account_id} on {check_date}")
                
                # Commit changes for this account
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Error backfilling rate usage for account {account.account_id}: {str(e)}")
                db.session.rollback()
                continue
        
        logger.info("Rate usage backfill completed")
        
    except Exception as e:
        logger.error(f"Error in rate usage backfill: {str(e)}")
        db.session.rollback()
