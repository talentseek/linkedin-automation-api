#!/usr/bin/env python3
"""
Simple script to create the webhook_data table.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.extensions import db
from src.models.webhook_data import WebhookData

def create_webhook_table():
    """Create the webhook_data table."""
    try:
        # Create the table
        WebhookData.__table__.create(db.engine, checkfirst=True)
        print("✅ webhook_data table created successfully!")
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")

if __name__ == "__main__":
    create_webhook_table()
