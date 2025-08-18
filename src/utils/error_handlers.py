"""
Global Error Handlers for Flask Application

This module provides global error handlers that catch unhandled exceptions
and return standardized error responses.
"""

import logging
from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException, NotFound, MethodNotAllowed
from sqlalchemy.exc import SQLAlchemyError
from .error_handling import (
    handle_exception,
    handle_not_found_error,
    handle_validation_error,
    create_error_response
)

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register global error handlers for the Flask application."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        return handle_not_found_error("Resource")
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        """Handle 405 Method Not Allowed errors."""
        return create_error_response(
            'BAD_REQUEST',
            f"Method {error.valid_methods[0] if error.valid_methods else 'GET'} not allowed for this endpoint",
            status_code=405
        )
    
    @app.errorhandler(400)
    def bad_request_error(error):
        """Handle 400 Bad Request errors."""
        return handle_validation_error("Invalid request data")
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        """Handle 401 Unauthorized errors."""
        return create_error_response('UNAUTHORIZED', "Authentication required", status_code=401)
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 Forbidden errors."""
        return create_error_response('FORBIDDEN', "Access denied", status_code=403)
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle 429 Rate Limit errors."""
        return create_error_response('RATE_LIMITED', "Rate limit exceeded", status_code=429)
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error."""
        return handle_exception(error, "request processing")
    
    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        """Handle SQLAlchemy database errors."""
        return handle_exception(error, "database operation")
    
    @app.errorhandler(Exception)
    def generic_error(error):
        """Handle all other unhandled exceptions."""
        return handle_exception(error, "request processing")
    
    @app.errorhandler(HTTPException)
    def http_error(error):
        """Handle HTTP exceptions."""
        return create_error_response(
            'BAD_REQUEST',
            error.description or "HTTP error occurred",
            status_code=error.code
        )

def log_request_error(error, request_info=None):
    """Log request errors with context information."""
    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'request_method': request_info.get('method') if request_info else 'Unknown',
        'request_path': request_info.get('path') if request_info else 'Unknown',
        'request_ip': request_info.get('ip') if request_info else 'Unknown'
    }
    
    logger.error(f"Request error: {error_context}")
