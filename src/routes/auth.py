from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Generate JWT token for API access."""
    try:
        data = request.get_json()
        
        if not data or 'api_key' not in data:
            return jsonify({'error': 'API key is required'}), 400
        
        # For now, we'll use a simple API key validation
        # In production, you should validate against a database or environment variable
        api_key = data['api_key']
        
        # Simple validation - in production, use proper API key management
        if api_key == 'linkedin-automation-api-key':
            # Create JWT token with 24 hour expiration
            access_token = create_access_token(
                identity='api-user',
                expires_delta=timedelta(hours=24)
            )
            
            return jsonify({
                'access_token': access_token,
                'token_type': 'Bearer',
                'expires_in': 86400  # 24 hours in seconds
            }), 200
        else:
            return jsonify({'error': 'Invalid API key'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/verify', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def verify_token():
    """Verify JWT token validity."""
    try:
        current_user = get_jwt_identity()
        return jsonify({
            'message': 'Token is valid',
            'user': current_user
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/refresh', methods=['POST'])
# @jwt_required()  # Temporarily removed for development
def refresh_token():
    """Refresh JWT token."""
    try:
        current_user = get_jwt_identity()
        new_token = create_access_token(
            identity=current_user,
            expires_delta=timedelta(hours=24)
        )
        
        return jsonify({
            'access_token': new_token,
            'token_type': 'Bearer',
            'expires_in': 86400
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

