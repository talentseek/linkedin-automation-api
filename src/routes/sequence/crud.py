"""
Basic CRUD operations for sequences.

This module contains functionality for:
- Getting campaign sequences
- Updating campaign sequences
- Getting example sequences
"""

import logging
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.extensions import db
from src.models import Campaign
from src.services.sequence_engine import SequenceEngine, EXAMPLE_SEQUENCE

logger = logging.getLogger(__name__)

# Import the blueprint from the package
from . import sequence_bp


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
