"""
Automation routes package - refactored from the monolithic automation.py file.

This package contains organized automation functionality:
- core.py: Main automation blueprint and core endpoints
- campaign_control.py: Campaign start/stop/pause functionality
- scheduler_control.py: Scheduler management endpoints
- testing.py: Testing and debugging endpoints
- notifications.py: Notification management endpoints
"""

from flask import Blueprint

# Create the main automation blueprint
automation_bp = Blueprint('automation', __name__)

# Import all route modules to register them
from . import core
from . import campaign_control
from . import scheduler_control
from . import testing
from . import notifications

# Export the blueprint
__all__ = ['automation_bp']
