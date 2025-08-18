"""
Sequence validation and testing.

This module contains functionality for:
- Sequence validation
- Sequence testing
- Delay testing
"""

import logging
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.extensions import db
from src.models import Campaign, Lead
from src.services.sequence_engine import SequenceEngine

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import sequence_bp


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
            'errors': validation_result.get('errors', []),
            'warnings': validation_result.get('warnings', [])
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating sequence: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/sequence/test-delays', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def test_sequence_delays():
    """Test sequence delays for a campaign."""
    try:
        data = request.get_json()
        if not data or 'campaign_id' not in data:
            return jsonify({'error': 'Campaign ID is required'}), 400
        
        campaign_id = data['campaign_id']
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        sequence_engine = SequenceEngine()
        sequence = campaign.sequence_json or []
        
        if not sequence:
            return jsonify({'error': 'Campaign has no sequence defined'}), 400
        
        # Test delays for each step
        delay_tests = []
        for i, step in enumerate(sequence):
            step_number = i + 1
            delay_minutes = step.get('delay_minutes', 0)
            
            # Calculate when this step would be sent
            if step_number == 1:
                # First step has no delay
                send_time = "Immediate"
            else:
                # Calculate cumulative delay
                cumulative_delay = sum(s.get('delay_minutes', 0) for s in sequence[:i])
                send_time = f"After {cumulative_delay} minutes"
            
            delay_tests.append({
                'step_number': step_number,
                'step_type': step.get('type', 'unknown'),
                'delay_minutes': delay_minutes,
                'send_time': send_time
            })
        
        return jsonify({
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'timezone': campaign.timezone or 'UTC',
            'total_steps': len(sequence),
            'delay_tests': delay_tests,
            'total_delay_minutes': sum(step.get('delay_minutes', 0) for step in sequence)
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing sequence delays: {str(e)}")
        return jsonify({'error': str(e)}), 500
