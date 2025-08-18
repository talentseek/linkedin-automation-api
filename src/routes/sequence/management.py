"""
Sequence management operations.

This module contains functionality for:
- Lead step management
- Next step calculation
- Step execution
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
        
        return jsonify({
            'lead_id': lead_id,
            'next_step': next_step,
            'sequence_complete': False
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting lead next step: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/leads/<lead_id>/execute-step', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def execute_lead_step(lead_id):
    """Execute the next step in the sequence for a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json() or {}
        step_number = data.get('step_number')
        
        sequence_engine = SequenceEngine()
        
        if step_number is not None:
            # Execute specific step
            result = sequence_engine.execute_step_for_lead(lead, step_number)
        else:
            # Execute next step
            result = sequence_engine.execute_next_step_for_lead(lead)
        
        if not result['success']:
            return jsonify({
                'error': 'Failed to execute step',
                'details': result.get('error', 'Unknown error')
            }), 400
        
        return jsonify({
            'message': 'Step executed successfully',
            'lead_id': lead_id,
            'step_executed': result.get('step_number'),
            'next_step': result.get('next_step'),
            'sequence_complete': result.get('sequence_complete', False)
        }), 200
        
    except Exception as e:
        logger.error(f"Error executing lead step: {str(e)}")
        return jsonify({'error': str(e)}), 500


@sequence_bp.route('/leads/<lead_id>/preview-step', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def preview_lead_step(lead_id):
    """Preview the next step in the sequence for a lead."""
    try:
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json() or {}
        step_number = data.get('step_number')
        
        sequence_engine = SequenceEngine()
        
        if step_number is not None:
            # Preview specific step
            preview = sequence_engine.preview_step_for_lead(lead, step_number)
        else:
            # Preview next step
            preview = sequence_engine.preview_next_step_for_lead(lead)
        
        if not preview:
            return jsonify({
                'lead_id': lead_id,
                'preview': None,
                'sequence_complete': True
            }), 200
        
        return jsonify({
            'lead_id': lead_id,
            'preview': preview,
            'sequence_complete': False
        }), 200
        
    except Exception as e:
        logger.error(f"Error previewing lead step: {str(e)}")
        return jsonify({'error': str(e)}), 500
