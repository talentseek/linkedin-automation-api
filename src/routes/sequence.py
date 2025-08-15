from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models import db, Campaign, Lead, LinkedInAccount
from src.services.sequence_engine import SequenceEngine, EXAMPLE_SEQUENCE
import logging
from datetime import datetime

sequence_bp = Blueprint('sequence', __name__)
logger = logging.getLogger(__name__)


@sequence_bp.route('/campaigns/<campaign_id>/sequence', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
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
# @jwt_required()  # Temporarily removed for development
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
# @jwt_required()  # Temporarily removed for development
def get_example_sequence():
    """Get an example sequence definition."""
    return jsonify({
        'example_sequence': EXAMPLE_SEQUENCE,
        'description': 'Example 3-step LinkedIn outreach sequence'
    }), 200


@sequence_bp.route('/leads/<lead_id>/next-step', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
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
# @jwt_required()  # Temporarily removed for development
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
# @jwt_required()  # Temporarily removed for development
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
# @jwt_required()  # Temporarily removed for development
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


@sequence_bp.route('/sequence/test-delays', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_sequence_delays():
    """Test sequence delay calculations with working days."""
    try:
        from src.services.sequence_engine import SequenceEngine
        
        data = request.get_json()
        sequence = data.get('sequence', EXAMPLE_SEQUENCE)
        
        sequence_engine = SequenceEngine()
        
        # Test delay calculations for each step
        delay_tests = []
        for step in sequence:
            delay_description = sequence_engine.get_delay_description(step)
            min_delay = sequence_engine._get_minimum_delay(step)
            
            delay_tests.append({
                'step_order': step.get('step_order'),
                'name': step.get('name'),
                'delay_hours': step.get('delay_hours', 0),
                'delay_working_days': step.get('delay_working_days', 0),
                'delay_description': delay_description,
                'total_delay_hours': min_delay.total_seconds() / 3600,
                'total_delay_days': min_delay.total_seconds() / 86400
            })
        
        return jsonify({
            'message': 'Sequence delay test completed',
            'delay_tests': delay_tests,
            'working_day_example': {
                'description': '3 working days from now',
                'target_date': sequence_engine._add_working_days(datetime.utcnow(), 3).isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing sequence delays: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/campaigns/<campaign_id>/timezone', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_campaign_timezone_info(campaign_id):
    """Get timezone information for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        
        timezone_info = sequence_engine.get_campaign_timezone_info(campaign)
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'timezone_info': timezone_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign timezone info: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/campaigns/<campaign_id>/timezone', methods=['PUT'])
# @jwt_required()  # Temporarily removed for development
def update_campaign_timezone(campaign_id):
    """Update the timezone for a campaign."""
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        data = request.get_json()
        new_timezone = data.get('timezone')
        
        if not new_timezone:
            return jsonify({'error': 'timezone is required'}), 400
        
        # Validate timezone
        try:
            import pytz
            pytz.timezone(new_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            return jsonify({'error': f'Invalid timezone: {new_timezone}'}), 400
        
        # Update timezone
        campaign.timezone = new_timezone
        db.session.commit()
        
        # Get updated timezone info
        from src.services.sequence_engine import SequenceEngine
        sequence_engine = SequenceEngine()
        timezone_info = sequence_engine.get_campaign_timezone_info(campaign)
        
        return jsonify({
            'message': 'Campaign timezone updated successfully',
            'campaign_id': campaign_id,
            'timezone': new_timezone,
            'timezone_info': timezone_info
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating campaign timezone: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/timezones/available', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_available_timezones():
    """Get a list of available timezones."""
    try:
        import pytz
        
        # Common timezones for business use
        common_timezones = [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Australia/Sydney',
            'Pacific/Auckland'
        ]
        
        timezone_list = []
        for tz_name in common_timezones:
            try:
                tz = pytz.timezone(tz_name)
                utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
                local_time = utc_now.astimezone(tz)
                
                timezone_list.append({
                    'name': tz_name,
                    'display_name': tz_name.replace('_', ' '),
                    'current_time': local_time.strftime('%H:%M'),
                    'utc_offset': local_time.strftime('%z'),
                    'is_weekend': local_time.weekday() >= 5
                })
            except Exception as e:
                logger.warning(f"Error processing timezone {tz_name}: {str(e)}")
        
        return jsonify({
            'timezones': timezone_list,
            'total': len(timezone_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting available timezones: {str(e)}")
        return jsonify({'error': str(e)}), 500

