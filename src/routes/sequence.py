from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Campaign, Lead, LinkedInAccount
from src.services.sequence_engine import SequenceEngine, EXAMPLE_SEQUENCE
import logging

sequence_bp = Blueprint('sequence', __name__)
logger = logging.getLogger(__name__)


@sequence_bp.route('/campaigns/<campaign_id>/sequence', methods=['PUT'])
@jwt_required()
def update_campaign_sequence(campaign_id):
    """Update the sequence definition for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        
        if not data or 'sequence' not in data:
            return jsonify({'error': 'Sequence definition is required'}), 400
        
        sequence_json = data['sequence']
        
        # Validate sequence definition
        sequence_engine = SequenceEngine()
        validation_result = sequence_engine.validate_sequence_definition(sequence_json)
        
        if not validation_result['valid']:
            return jsonify({
                'error': 'Invalid sequence definition',
                'validation_errors': validation_result['errors']
            }), 400
        
        # Update campaign sequence
        campaign.sequence_json = sequence_json
        db.session.commit()
        
        return jsonify({
            'message': 'Campaign sequence updated successfully',
            'campaign': campaign.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating campaign sequence: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/campaigns/<campaign_id>/sequence', methods=['GET'])
@jwt_required()
def get_campaign_sequence(campaign_id):
    """Get the sequence definition for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        return jsonify({
            'campaign_id': campaign_id,
            'sequence': campaign.sequence_json or [],
            'has_sequence': campaign.sequence_json is not None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign sequence: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/sequence/example', methods=['GET'])
@jwt_required()
def get_example_sequence():
    """Get an example sequence definition."""
    return jsonify({
        'example_sequence': EXAMPLE_SEQUENCE,
        'description': 'Example 3-step LinkedIn outreach sequence'
    }), 200


@sequence_bp.route('/leads/<lead_id>/next-step', methods=['GET'])
@jwt_required()
def get_lead_next_step(lead_id):
    """Get the next step in the sequence for a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        sequence_engine = SequenceEngine()
        next_step = sequence_engine.get_next_step_for_lead(lead)
        
        if not next_step:
            return jsonify({
                'lead_id': lead_id,
                'next_step': None,
                'sequence_complete': True
            }), 200
        
        # Check if step can be executed
        can_execute_result = sequence_engine.can_execute_step(lead, next_step)
        
        return jsonify({
            'lead_id': lead_id,
            'next_step': next_step,
            'can_execute': can_execute_result['can_execute'],
            'execution_reason': can_execute_result['reason'],
            'sequence_complete': False
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting next step for lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/leads/<lead_id>/execute-step', methods=['POST'])
@jwt_required()
def execute_lead_step(lead_id):
    """Execute the next step in the sequence for a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json()
        
        if not data or 'linkedin_account_id' not in data:
            return jsonify({'error': 'LinkedIn account ID is required'}), 400
        
        linkedin_account_id = data['linkedin_account_id']
        
        # Verify LinkedIn account exists and belongs to the same client
        linkedin_account = LinkedInAccount.query.filter_by(
            id=linkedin_account_id,
            client_id=lead.campaign.client_id
        ).first()
        
        if not linkedin_account:
            return jsonify({'error': 'LinkedIn account not found or not authorized'}), 404
        
        if linkedin_account.status != 'connected':
            return jsonify({'error': 'LinkedIn account is not connected'}), 400
        
        sequence_engine = SequenceEngine()
        
        # Get next step
        next_step = sequence_engine.get_next_step_for_lead(lead)
        if not next_step:
            return jsonify({'error': 'No next step available for this lead'}), 400
        
        # Check if step can be executed
        can_execute_result = sequence_engine.can_execute_step(lead, next_step)
        if not can_execute_result['can_execute']:
            return jsonify({
                'error': 'Step cannot be executed',
                'reason': can_execute_result['reason']
            }), 400
        
        # Execute the step
        execution_result = sequence_engine.execute_step(lead, next_step, linkedin_account)
        
        if execution_result['success']:
            return jsonify({
                'message': 'Step executed successfully',
                'lead': lead.to_dict(),
                'execution_result': execution_result
            }), 200
        else:
            return jsonify({
                'error': 'Step execution failed',
                'execution_result': execution_result
            }), 400
        
    except Exception as e:
        logger.error(f"Error executing step for lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/leads/<lead_id>/preview-step', methods=['POST'])
@jwt_required()
def preview_lead_step(lead_id):
    """Preview the personalized message for the next step without executing it."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        sequence_engine = SequenceEngine()
        
        # Get next step
        next_step = sequence_engine.get_next_step_for_lead(lead)
        if not next_step:
            return jsonify({'error': 'No next step available for this lead'}), 400
        
        # Personalize the template
        template = next_step.get('template', '')
        personalized_message = sequence_engine.personalize_template(template, lead)
        
        return jsonify({
            'lead_id': lead_id,
            'step': next_step,
            'original_template': template,
            'personalized_message': personalized_message,
            'personalization_data': {
                'first_name': lead.first_name or 'there',
                'last_name': lead.last_name or '',
                'full_name': lead.full_name,
                'company_name': lead.company_name or 'your company'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error previewing step for lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/sequence/validate', methods=['POST'])
@jwt_required()
def validate_sequence():
    """Validate a sequence definition."""
    try:
        data = request.get_json()
        
        if not data or 'sequence' not in data:
            return jsonify({'error': 'Sequence definition is required'}), 400
        
        sequence_json = data['sequence']
        
        sequence_engine = SequenceEngine()
        validation_result = sequence_engine.validate_sequence_definition(sequence_json)
        
        return jsonify({
            'valid': validation_result['valid'],
            'errors': validation_result['errors']
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating sequence: {str(e)}")
        return jsonify({'error': str(e)}), 500

