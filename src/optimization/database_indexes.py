"""
Database Index Optimization Script

This script adds missing indexes to improve query performance for common operations.
"""

import logging
from sqlalchemy import text
from src.extensions import db

logger = logging.getLogger(__name__)

def create_performance_indexes():
    """Create performance indexes for common queries."""
    
    indexes = [
        # Lead table indexes
        {
            'name': 'ix_leads_campaign_status',
            'table': 'leads',
            'columns': ['campaign_id', 'status'],
            'description': 'Index for filtering leads by campaign and status'
        },
        {
            'name': 'ix_leads_status_created',
            'table': 'leads',
            'columns': ['status', 'created_at'],
            'description': 'Index for status-based queries with date filtering'
        },
        {
            'name': 'ix_leads_public_identifier',
            'table': 'leads',
            'columns': ['public_identifier'],
            'description': 'Index for lead lookup by LinkedIn public identifier'
        },
        {
            'name': 'ix_leads_conversation_id',
            'table': 'leads',
            'columns': ['conversation_id'],
            'description': 'Index for conversation-based lookups'
        },
        {
            'name': 'ix_leads_last_step_sent',
            'table': 'leads',
            'columns': ['last_step_sent_at'],
            'description': 'Index for scheduler queries based on last step sent'
        },
        
        # Event table indexes
        {
            'name': 'ix_events_lead_timestamp',
            'table': 'events',
            'columns': ['lead_id', 'timestamp'],
            'description': 'Index for event queries by lead and time'
        },
        {
            'name': 'ix_events_type_timestamp',
            'table': 'events',
            'columns': ['event_type', 'timestamp'],
            'description': 'Index for event type filtering with time'
        },
        {
            'name': 'ix_events_timestamp',
            'table': 'events',
            'columns': ['timestamp'],
            'description': 'Index for time-based event queries'
        },
        
        # Campaign table indexes
        {
            'name': 'ix_campaigns_client_status',
            'table': 'campaigns',
            'columns': ['client_id', 'status'],
            'description': 'Index for client campaigns by status'
        },
        {
            'name': 'ix_campaigns_status_created',
            'table': 'campaigns',
            'columns': ['status', 'created_at'],
            'description': 'Index for active campaigns with date filtering'
        },
        
        # Client table indexes
        {
            'name': 'ix_clients_email',
            'table': 'clients',
            'columns': ['email'],
            'description': 'Index for client lookup by email'
        },
        
        # LinkedIn Account table indexes
        {
            'name': 'ix_linkedin_accounts_client_status',
            'table': 'linkedin_accounts',
            'columns': ['client_id', 'status'],
            'description': 'Index for client accounts by status'
        },
        {
            'name': 'ix_linkedin_accounts_account_id',
            'table': 'linkedin_accounts',
            'columns': ['account_id'],
            'description': 'Index for account lookup by Unipile account ID'
        },
        
        # Webhook Data table indexes
        {
            'name': 'ix_webhook_data_timestamp',
            'table': 'webhook_data',
            'columns': ['timestamp'],
            'description': 'Index for time-based webhook queries'
        },
        {
            'name': 'ix_webhook_data_method_timestamp',
            'table': 'webhook_data',
            'columns': ['method', 'timestamp'],
            'description': 'Index for webhook queries by method and time'
        }
    ]
    
    created_count = 0
    skipped_count = 0
    
    for index in indexes:
        try:
            # Check if index already exists
            check_sql = f"""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = '{index['name']}' 
            AND tablename = '{index['table']}'
            """
            
            result = db.session.execute(text(check_sql)).fetchone()
            
            if result:
                logger.info(f"Index {index['name']} already exists, skipping")
                skipped_count += 1
                continue
            
            # Create index
            columns_str = ', '.join(index['columns'])
            create_sql = f"""
            CREATE INDEX CONCURRENTLY {index['name']} 
            ON {index['table']} ({columns_str})
            """
            
            db.session.execute(text(create_sql))
            db.session.commit()
            logger.info(f"Created index {index['name']} on {index['table']} ({columns_str})")
            created_count += 1
            
        except Exception as e:
            logger.error(f"Failed to create index {index['name']}: {str(e)}")
    
    logger.info(f"Index creation complete: {created_count} created, {skipped_count} skipped")
    return created_count, skipped_count

def create_composite_indexes():
    """Create composite indexes for complex queries."""
    
    composite_indexes = [
        # Lead processing queries
        {
            'name': 'ix_leads_scheduler_processing',
            'table': 'leads',
            'columns': ['campaign_id', 'status', 'current_step', 'last_step_sent_at'],
            'description': 'Composite index for scheduler lead processing'
        },
        
        # Analytics queries
        {
            'name': 'ix_events_analytics',
            'table': 'events',
            'columns': ['event_type', 'timestamp', 'lead_id'],
            'description': 'Composite index for analytics queries'
        },
        
        # Campaign status queries
        {
            'name': 'ix_campaigns_analytics',
            'table': 'campaigns',
            'columns': ['client_id', 'status', 'created_at'],
            'description': 'Composite index for campaign analytics'
        }
    ]
    
    created_count = 0
    
    for index in composite_indexes:
        try:
            # Check if index already exists
            check_sql = f"""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = '{index['name']}' 
            AND tablename = '{index['table']}'
            """
            
            result = db.session.execute(text(check_sql)).fetchone()
            
            if result:
                logger.info(f"Composite index {index['name']} already exists, skipping")
                continue
            
            # Create composite index
            columns_str = ', '.join(index['columns'])
            create_sql = f"""
            CREATE INDEX CONCURRENTLY {index['name']} 
            ON {index['table']} ({columns_str})
            """
            
            db.session.execute(text(create_sql))
            db.session.commit()
            logger.info(f"Created composite index {index['name']} on {index['table']} ({columns_str})")
            created_count += 1
            
        except Exception as e:
            logger.error(f"Failed to create composite index {index['name']}: {str(e)}")
    
    logger.info(f"Composite index creation complete: {created_count} created")
    return created_count

def optimize_database():
    """Run all database optimizations."""
    logger.info("Starting database optimization...")
    
    # Create basic indexes
    basic_created, basic_skipped = create_performance_indexes()
    
    # Create composite indexes
    composite_created = create_composite_indexes()
    
    # Update table statistics
    try:
        tables = ['leads', 'events', 'campaigns', 'clients', 'linkedin_accounts', 'webhook_data', 'rate_usage']
        for table in tables:
            db.session.execute(text(f"ANALYZE {table}"))
            logger.info(f"Updated statistics for {table}")
    except Exception as e:
        logger.error(f"Failed to update table statistics: {str(e)}")
    
    total_created = basic_created + composite_created
    logger.info(f"Database optimization complete: {total_created} indexes created, {basic_skipped} skipped")
    
    return {
        'basic_indexes_created': basic_created,
        'basic_indexes_skipped': basic_skipped,
        'composite_indexes_created': composite_created,
        'total_created': total_created
    }

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run optimization
    with db.app.app_context():
        results = optimize_database()
        print(f"Optimization results: {results}")
