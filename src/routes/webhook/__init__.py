"""
Webhook routes package - refactored from the monolithic webhook.py file.

This package contains organized webhook management endpoints:
- handlers.py: Main webhook event handlers
- unipile.py: Unipile-specific webhook endpoints
- health.py: Health check and status endpoints
- debug.py: Debug and testing endpoints
- management.py: Webhook management operations
"""

from flask import Blueprint

# Create the main webhook blueprint
webhook_bp = Blueprint('webhook', __name__)

# Import all route modules to register them
from . import handlers
# from . import unipile  # Temporarily disabled for debugging
from . import health
from . import debug
from . import management

# Export the blueprint
__all__ = ['webhook_bp']
