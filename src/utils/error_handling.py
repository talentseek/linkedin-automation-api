"""
Standardized Error Handling Utilities

This module provides consistent error response formats and error handling
functions across all API endpoints.
"""

import logging
from typing import Dict, Any, Optional, Union
from flask import jsonify, current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

# Standard error codes
ERROR_CODES = {
    # Client errors (4xx)
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'NOT_FOUND': 'NOT_FOUND',
    'CONFLICT': 'CONFLICT',
    'UNAUTHORIZED': 'UNAUTHORIZED',
    'FORBIDDEN': 'FORBIDDEN',
    'RATE_LIMITED': 'RATE_LIMITED',
    'BAD_REQUEST': 'BAD_REQUEST',
    
    # Server errors (5xx)
    'INTERNAL_ERROR': 'INTERNAL_ERROR',
    'SERVICE_UNAVAILABLE': 'SERVICE_UNAVAILABLE',
    'DATABASE_ERROR': 'DATABASE_ERROR',
    'EXTERNAL_API_ERROR': 'EXTERNAL_API_ERROR',
    
    # Business logic errors
    'CAMPAIGN_NOT_ACTIVE': 'CAMPAIGN_NOT_ACTIVE',
    'LEAD_ALREADY_EXISTS': 'LEAD_ALREADY_EXISTS',
    'RATE_LIMIT_EXCEEDED': 'RATE_LIMIT_EXCEEDED',
    'INVALID_SEQUENCE': 'INVALID_SEQUENCE',
    'WEBHOOK_ERROR': 'WEBHOOK_ERROR'
}

# HTTP status code mapping
STATUS_CODES = {
    'VALIDATION_ERROR': 400,
    'NOT_FOUND': 404,
    'CONFLICT': 409,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'RATE_LIMITED': 429,
    'BAD_REQUEST': 400,
    'INTERNAL_ERROR': 500,
    'SERVICE_UNAVAILABLE': 503,
    'DATABASE_ERROR': 500,
    'EXTERNAL_API_ERROR': 502,
    'CAMPAIGN_NOT_ACTIVE': 400,
    'LEAD_ALREADY_EXISTS': 409,
    'RATE_LIMIT_EXCEEDED': 429,
    'INVALID_SEQUENCE': 400,
    'WEBHOOK_ERROR': 400
}

def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None
) -> tuple:
    """
    Create a standardized error response.
    
    Args:
        code: Error code from ERROR_CODES
        message: Human-readable error message
        details: Additional error details (optional)
        status_code: HTTP status code (optional, defaults to code mapping)
    
    Returns:
        Tuple of (json_response, status_code)
    """
    if code not in ERROR_CODES:
        code = 'INTERNAL_ERROR'
        logger.warning(f"Unknown error code used: {code}, defaulting to INTERNAL_ERROR")
    
    http_status = status_code or STATUS_CODES.get(code, 500)
    
    error_response = {
        'error': {
            'code': code,
            'message': message,
            'timestamp': current_app.config.get('TIMESTAMP_FORMAT', 'iso')
        }
    }
    
    if details:
        error_response['error']['details'] = details
    
    return jsonify(error_response), http_status

def handle_validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> tuple:
    """Handle validation errors (400)."""
    return create_error_response('VALIDATION_ERROR', message, details)

def handle_not_found_error(resource: str, resource_id: Optional[str] = None) -> tuple:
    """Handle not found errors (404)."""
    message = f"{resource} not found"
    if resource_id:
        message += f" with id: {resource_id}"
    return create_error_response('NOT_FOUND', message)

def handle_conflict_error(message: str, details: Optional[Dict[str, Any]] = None) -> tuple:
    """Handle conflict errors (409)."""
    return create_error_response('CONFLICT', message, details)

def handle_unauthorized_error(message: str = "Authentication required") -> tuple:
    """Handle unauthorized errors (401)."""
    return create_error_response('UNAUTHORIZED', message)

def handle_forbidden_error(message: str = "Access denied") -> tuple:
    """Handle forbidden errors (403)."""
    return create_error_response('FORBIDDEN', message)

def handle_rate_limit_error(message: str = "Rate limit exceeded") -> tuple:
    """Handle rate limit errors (429)."""
    return create_error_response('RATE_LIMITED', message)

def handle_database_error(error: Exception, operation: str = "database operation") -> tuple:
    """Handle database errors (500)."""
    logger.error(f"Database error during {operation}: {str(error)}")
    
    if isinstance(error, IntegrityError):
        return create_error_response('CONFLICT', f"Database constraint violation during {operation}")
    elif isinstance(error, SQLAlchemyError):
        return create_error_response('DATABASE_ERROR', f"Database error during {operation}")
    else:
        return create_error_response('DATABASE_ERROR', f"Unexpected database error during {operation}")

def handle_external_api_error(error: Exception, service: str = "external service") -> tuple:
    """Handle external API errors (502)."""
    logger.error(f"External API error with {service}: {str(error)}")
    return create_error_response('EXTERNAL_API_ERROR', f"Error communicating with {service}")

def handle_internal_error(error: Exception, operation: str = "operation") -> tuple:
    """Handle internal server errors (500)."""
    logger.error(f"Internal error during {operation}: {str(error)}")
    return create_error_response('INTERNAL_ERROR', f"An unexpected error occurred during {operation}")

def handle_business_logic_error(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> tuple:
    """Handle business logic errors."""
    return create_error_response(code, message, details)

def handle_exception(error: Exception, operation: str = "operation") -> tuple:
    """
    Generic exception handler that categorizes errors and returns appropriate responses.
    
    Args:
        error: The exception that occurred
        operation: Description of the operation being performed
    
    Returns:
        Tuple of (json_response, status_code)
    """
    if isinstance(error, HTTPException):
        return create_error_response('BAD_REQUEST', error.description, status_code=error.code)
    elif isinstance(error, IntegrityError):
        return handle_database_error(error, operation)
    elif isinstance(error, SQLAlchemyError):
        return handle_database_error(error, operation)
    elif isinstance(error, ValueError):
        return handle_validation_error(str(error))
    elif isinstance(error, KeyError):
        return handle_validation_error(f"Missing required field: {str(error)}")
    elif isinstance(error, TypeError):
        return handle_validation_error(f"Invalid data type: {str(error)}")
    else:
        return handle_internal_error(error, operation)

def log_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Log an error with context information.
    
    Args:
        error: The exception that occurred
        context: Additional context information
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context or {}
    }
    
    logger.error(f"Error occurred: {error_info}")

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> Optional[tuple]:
    """
    Validate that required fields are present in request data.
    
    Args:
        data: Request data dictionary
        required_fields: List of required field names
    
    Returns:
        Error response tuple if validation fails, None if validation passes
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        details = {
            'missing_fields': missing_fields,
            'required_fields': required_fields
        }
        return handle_validation_error(
            f"Missing required fields: {', '.join(missing_fields)}",
            details
        )
    
    return None

def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> Optional[tuple]:
    """
    Validate that fields have the correct types.
    
    Args:
        data: Request data dictionary
        field_types: Dictionary mapping field names to expected types
    
    Returns:
        Error response tuple if validation fails, None if validation passes
    """
    type_errors = []
    
    for field, expected_type in field_types.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                type_errors.append({
                    'field': field,
                    'expected_type': expected_type.__name__,
                    'actual_type': type(data[field]).__name__
                })
    
    if type_errors:
        details = {'type_errors': type_errors}
        return handle_validation_error(
            f"Invalid field types: {len(type_errors)} field(s) have incorrect types",
            details
        )
    
    return None
