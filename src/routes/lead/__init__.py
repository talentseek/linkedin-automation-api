"""
Lead routes package - refactored from the monolithic lead.py file.

This package contains organized lead management endpoints:
- crud.py: Basic CRUD operations
- import_search.py: Lead import and search functionality
- search_params.py: Search parameters and helpers
- management.py: Lead management operations
- first_level.py: First level connections handling
"""

from flask import Blueprint

# Create the main lead blueprint
lead_bp = Blueprint('lead', __name__)

# Import all route modules to register them
from . import crud
from . import import_search
from . import search_params
from . import management
from . import first_level

# Export the blueprint
__all__ = ['lead_bp']
