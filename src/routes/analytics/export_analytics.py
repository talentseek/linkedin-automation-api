"""
CSV export functionality.

This module contains functionality for:
- Exporting leads data to CSV
- Exporting events data to CSV
- Exporting analytics data to CSV
"""

import logging
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, send_file, current_app

from src.extensions import db
from src.models import Campaign, Lead, Event

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import analytics_bp


@analytics_bp.route('/campaigns/<campaign_id>/export/csv', methods=['GET'])
def export_campaign_csv(campaign_id):
    """Export campaign data to CSV."""
    try:
        # Get query parameters
        data_type = request.args.get('type', 'leads')  # leads, events, analytics
        days = request.args.get('days', 30, type=int)
        
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Generate CSV based on data type
        if data_type == 'leads':
            csv_data = _export_leads_csv(campaign)
        elif data_type == 'events':
            csv_data = _export_events_csv(campaign, days)
        elif data_type == 'analytics':
            csv_data = _export_analytics_csv(campaign, days)
        else:
            return jsonify({'error': 'Invalid data type. Use: leads, events, or analytics'}), 400
        
        # Create file response
        filename = f"campaign_{campaign_id}_{data_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error exporting campaign CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _export_leads_csv(campaign):
    """Export leads data to CSV."""
    try:
        # Get all leads for the campaign
        leads = Lead.query.filter_by(campaign_id=campaign.id).all()
        
        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Lead ID',
            'First Name',
            'Last Name',
            'Company Name',
            'Public Identifier',
            'Status',
            'Connection Type',
            'Current Step',
            'Created At',
            'Connected At',
            'Last Message Sent At',
            'Invite Sent At'
        ])
        
        # Write data
        for lead in leads:
            writer.writerow([
                lead.id,
                lead.first_name or '',
                lead.last_name or '',
                lead.company_name or '',
                lead.public_identifier or '',
                lead.status or '',
                lead.connection_type or '',
                lead.current_step or 0,
                lead.created_at.isoformat() if lead.created_at else '',
                lead.connected_at.isoformat() if lead.connected_at else '',
                lead.last_message_sent_at.isoformat() if lead.last_message_sent_at else '',
                lead.invite_sent_at.isoformat() if lead.invite_sent_at else ''
            ])
        
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error exporting leads CSV: {str(e)}")
        raise


def _export_events_csv(campaign, days=30):
    """Export events data to CSV."""
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get events for the campaign
        events = Event.query.join(Lead).filter(
            Lead.campaign_id == campaign.id,
            Event.timestamp >= start_date
        ).order_by(Event.timestamp.desc()).all()
        
        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Event ID',
            'Lead ID',
            'Event Type',
            'Timestamp',
            'Meta JSON'
        ])
        
        # Write data
        for event in events:
            writer.writerow([
                event.id,
                event.lead_id,
                event.event_type,
                event.timestamp.isoformat(),
                str(event.meta_json) if event.meta_json else ''
            ])
        
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error exporting events CSV: {str(e)}")
        raise


def _export_analytics_csv(campaign, days=30):
    """Export analytics data to CSV."""
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get leads for the campaign
        leads = Lead.query.filter(
            Lead.campaign_id == campaign.id,
            Lead.created_at >= start_date
        ).all()
        
        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Date',
            'New Leads',
            'Invites Sent',
            'Connections Made',
            'Messages Sent',
            'Responses Received',
            'Completions'
        ])
        
        # Group leads by date
        leads_by_date = {}
        for lead in leads:
            date_key = lead.created_at.date()
            if date_key not in leads_by_date:
                leads_by_date[date_key] = {
                    'new_leads': 0,
                    'invites_sent': 0,
                    'connections_made': 0,
                    'messages_sent': 0,
                    'responses_received': 0,
                    'completions': 0
                }
            
            leads_by_date[date_key]['new_leads'] += 1
            
            # Count status changes
            if lead.status in ['invite_sent', 'invited']:
                leads_by_date[date_key]['invites_sent'] += 1
            if lead.status in ['connected', 'messaged', 'responded', 'completed']:
                leads_by_date[date_key]['connections_made'] += 1
            if lead.status in ['messaged', 'responded', 'completed']:
                leads_by_date[date_key]['messages_sent'] += 1
            if lead.status in ['responded', 'completed']:
                leads_by_date[date_key]['responses_received'] += 1
            if lead.status == 'completed':
                leads_by_date[date_key]['completions'] += 1
        
        # Write data
        for date_key in sorted(leads_by_date.keys()):
            data = leads_by_date[date_key]
            writer.writerow([
                date_key.isoformat(),
                data['new_leads'],
                data['invites_sent'],
                data['connections_made'],
                data['messages_sent'],
                data['responses_received'],
                data['completions']
            ])
        
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error exporting analytics CSV: {str(e)}")
        raise
