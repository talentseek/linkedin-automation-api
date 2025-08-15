"""
Testing and debugging endpoints.

⚠️  SECURITY WARNING: All test endpoints should be SIMULATION ONLY.
⚠️  NO REAL MESSAGES OR CONNECTION REQUESTS should be sent during testing.
⚠️  All test endpoints must be disabled in production.
"""

from flask import request, jsonify
from src.routes.automation import automation_bp
from src.models.lead import Lead
from src.models.campaign import Campaign
from src.models.linkedin_account import LinkedInAccount
from src.services.sequence_engine import SequenceEngine
from src.services.scheduler import get_outreach_scheduler
import logging

logger = logging.getLogger(__name__)


@automation_bp.route('/leads/<lead_id>/schedule-step', methods=['POST'])
def schedule_lead_step(lead_id):
    """Schedule a lead for the next step."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        scheduler = get_outreach_scheduler()
        scheduler.schedule_lead_step(lead_id, None)
        
        return jsonify({
            'success': True,
            'message': f'Lead {lead_id} scheduled for next step',
            'lead_status': lead.status,
            'current_step': lead.current_step
        })
        
    except Exception as e:
        logger.error(f"Error scheduling lead step: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/process-leads', methods=['POST'])
def test_process_leads():
    """Test processing leads (SIMULATION ONLY)."""
    try:
        scheduler = get_outreach_scheduler()
        
        # Get leads that would be processed
        leads = Lead.query.filter(
            Lead.status.in_(['pending_invite', 'connected', 'messaged'])
        ).all()
        
        ready_leads = []
        for lead in leads:
            if scheduler._is_lead_ready_for_processing(lead):
                ready_leads.append({
                    'id': lead.id,
                    'name': f"{lead.first_name} {lead.last_name}",
                    'status': lead.status,
                    'current_step': lead.current_step,
                    'company': lead.company_name
                })
        
        return jsonify({
            'success': True,
            'total_leads': len(leads),
            'ready_leads': ready_leads,
            'ready_count': len(ready_leads),
            'note': 'This was a simulation - no real processing occurred'
        })
        
    except Exception as e:
        logger.error(f"Error testing lead processing: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/sequence-debug', methods=['POST'])
def test_sequence_debug():
    """Test sequence debugging (SIMULATION ONLY)."""
    try:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required'}), 400
        
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        sequence_engine = SequenceEngine()
        sequence_info = sequence_engine.get_sequence_info(campaign.sequence_json)
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'sequence_info': sequence_info,
            'note': 'This was a simulation - no real sequence execution occurred'
        })
        
    except Exception as e:
        logger.error(f"Error testing sequence debug: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/ready-check', methods=['POST'])
def test_ready_check():
    """Test lead ready check (SIMULATION ONLY)."""
    try:
        data = request.get_json() or {}
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({'error': 'lead_id is required'}), 400
        
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        scheduler = get_outreach_scheduler()
        is_ready = scheduler._is_lead_ready_for_processing(lead)
        
        return jsonify({
            'lead_id': lead_id,
            'lead_name': f"{lead.first_name} {lead.last_name}",
            'status': lead.status,
            'current_step': lead.current_step,
            'is_ready': is_ready,
            'note': 'This was a simulation - no real processing occurred'
        })
        
    except Exception as e:
        logger.error(f"Error testing ready check: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/reset-leads', methods=['POST'])
def test_reset_leads():
    """Test resetting leads (SIMULATION ONLY)."""
    try:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required'}), 400
        
        # Get leads for this campaign
        leads = Lead.query.filter_by(campaign_id=campaign_id).all()
        
        reset_count = 0
        for lead in leads:
            if lead.status in ['error', 'completed']:
                reset_count += 1
                # In simulation, we just count what would be reset
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_leads': len(leads),
            'would_reset': reset_count,
            'note': 'This was a simulation - no leads were actually reset'
        })
        
    except Exception as e:
        logger.error(f"Error testing lead reset: {str(e)}")
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/test/format-message', methods=['POST'])
def test_format_message():
    """Test message formatting (SIMULATION ONLY)."""
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
