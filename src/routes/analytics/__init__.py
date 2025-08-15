"""
Analytics routes package - refactored from the monolithic analytics.py file.

This package contains organized analytics functionality:
- core.py: Main analytics blueprint and core endpoints
- campaign_analytics.py: Campaign-specific analytics endpoints
- weekly_statistics.py: Weekly statistics and reporting endpoints
- export_analytics.py: CSV export functionality
- comparative_analytics.py: Comparative analytics across campaigns/clients
- real_time_analytics.py: Real-time activity monitoring
"""

from flask import Blueprint

# Create the main analytics blueprint
analytics_bp = Blueprint('analytics', __name__)

# Import all route modules to register them
from . import core
from . import campaign_analytics
from . import weekly_statistics
from . import export_analytics
from . import comparative_analytics
from . import real_time_analytics

# Export the blueprint
__all__ = ['analytics_bp']
