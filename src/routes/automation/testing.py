"""
Testing and debugging endpoints.

⚠️  SECURITY WARNING: All test endpoints should be SIMULATION ONLY.
⚠️  NO REAL MESSAGES OR CONNECTION REQUESTS should be sent during testing.
⚠️  All test endpoints must be disabled in production.
"""

This module contains functionality for:
- Lead processing tests
- Sequence debugging
- Message formatting tests
- Step execution tests
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import jsonify, request, current_app

from src.extensions import db
from src.models import Campaign, Lead, Event, LinkedInAccount, Client
from src.services.scheduler import get_outreach_scheduler
from src.services.sequence_engine import SequenceEngine

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import automation_bp


@automation_bp.route('/leads/<lead_id>/schedule-step', methods=['POST'])
def schedule_lead_step(lead_id):
    """Schedule a lead for the next step."""
    try:
        # Get lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get scheduler
        scheduler = get_outreach_scheduler()
        
        # Schedule the lead step
        scheduler.schedule_lead_step(lead_id, None)  # linkedin_account_id not needed for scheduling
        
        return jsonify({
            'message': 'Lead step scheduled successfully',
            'lead_id': lead_id,
            'current_step': lead.current_step,
            'status': lead.status
        })
        
    except Exception as e:
        logger.error(f"Error scheduling lead step: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/process-leads', methods=['POST'])
def test_process_leads():
    """Test processing leads for a campaign."""
    try:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required'}), 400
        
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get leads that are ready for processing
        leads = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.status.in_(['pending_invite', 'connected', 'messaged'])
        ).all()
        
        results = []
        for lead in leads:
            try:
                # Check if lead is ready for processing
                scheduler = get_outreach_scheduler()
                is_ready = scheduler._is_lead_ready_for_processing(lead)
                
                results.append({
                    'lead_id': lead.id,
                    'status': lead.status,
                    'current_step': lead.current_step,
                    'is_ready': is_ready,
                    'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None
                })
                
            except Exception as e:
                results.append({
                    'lead_id': lead.id,
                    'error': str(e)
                })
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_leads': len(leads),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error testing lead processing: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/sequence-debug', methods=['POST'])
def test_sequence_debug():
    """Test sequence debugging for a campaign."""
    try:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required'}), 400
        
        # Get campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get sequence engine
        sequence_engine = SequenceEngine()
        
        # Validate sequence
        sequence = campaign.sequence_json
        validation = sequence_engine.validate_sequence(sequence)
        
        # Get sequence info
        sequence_info = sequence_engine.get_sequence_info(campaign)
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'sequence_validation': validation,
            'sequence_info': sequence_info,
            'sequence': sequence
        })
        
    except Exception as e:
        logger.error(f"Error testing sequence debug: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/ready-check', methods=['POST'])
def test_ready_check():
    """Test lead readiness check."""
    try:
        data = request.get_json() or {}
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        # Get lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get scheduler
        scheduler = get_outreach_scheduler()
        
        # Check if lead is ready
        is_ready = scheduler._is_lead_ready_for_processing(lead)
        
        return jsonify({
            'lead_id': lead_id,
            'lead_status': lead.status,
            'current_step': lead.current_step,
            'is_ready': is_ready,
            'last_step_sent_at': lead.last_step_sent_at.isoformat() if lead.last_step_sent_at else None
        })
        
    except Exception as e:
        logger.error(f"Error testing ready check: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/reset-leads', methods=['POST'])
def test_reset_leads():
    """Reset leads for testing purposes."""
    try:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required'}), 400
        
        # Get leads for the campaign
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        
        reset_count = 0
        for lead in leads:
            # Reset lead to initial state
            lead.status = 'pending_invite'
            lead.current_step = 0
            lead.last_step_sent_at = None
            lead.invite_sent_at = None
            lead.connected_at = None
            lead.last_message_sent_at = None
            reset_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Reset {reset_count} leads successfully',
            'campaign_id': campaign_id,
            'reset_count': reset_count
        })
        
    except Exception as e:
        logger.error(f"Error resetting leads: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/format-message', methods=['POST'])
def test_format_message():
    """Test message formatting with lead data."""
    try:
        data = request.get_json() or {}
        lead_id = data.get('lead_id')
        message = data.get('message')
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        if not message:
            return jsonify({'error': 'message is required'}), 400
        
        # Get lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get sequence engine
        sequence_engine = SequenceEngine()
        
        # Format message
        formatted_message = sequence_engine._format_message(message, lead)
        
        return jsonify({
            'lead_id': lead_id,
            'original_message': message,
            'formatted_message': formatted_message,
            'lead_data': {
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'company_name': lead.company_name,
                'status': lead.status
            }
        })
        
    except Exception as e:
        logger.error(f"Error testing message formatting: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/execute-step', methods=['POST'])
def test_execute_step():
    """Test executing a step for a lead (SIMULATION ONLY - NO REAL ACTIONS)."""
    try:
        data = request.get_json() or {}
        lead_id = data.get('lead_id')
        step_data = data.get('step')
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        if not step_data:
            return jsonify({'error': 'step is required'}), 400
        
        # Get lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get campaign and LinkedIn account
        campaign = Campaign.query.get(lead.campaign_id)
        linkedin_account = LinkedInAccount.query.filter_by(
            client_id=campaign.client_id,
            status='connected'
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'No connected LinkedIn account found'}), 400
        
        # Get sequence engine
        sequence_engine = SequenceEngine()
        
        # SIMULATION ONLY - Format message but don't send
        action_type = step_data.get('action_type')
        message = step_data.get('message', '')
        formatted_message = sequence_engine._format_message(message, lead)
        
        # Create simulation result
        simulation_result = {
            'success': True,
            'simulation': True,
            'action_type': action_type,
            'original_message': message,
            'formatted_message': formatted_message,
            'would_send_to': {
                'lead_id': lead.id,
                'lead_name': f"{lead.first_name} {lead.last_name}",
                'linkedin_account': linkedin_account.account_id
            },
            'note': 'This was a simulation - no real message was sent'
        }
        
        return jsonify({
            'lead_id': lead_id,
            'step_data': step_data,
            'result': simulation_result,
            'lead_status_after': lead.status,
            'current_step_after': lead.current_step,
            'simulation': True
        })
        
    except Exception as e:
        logger.error(f"Error testing step execution: {str(e)}")
        return jsonify({'error': str(e)}), 500
