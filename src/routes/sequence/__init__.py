"""
Sequence routes package - refactored from the monolithic sequence.py file.

This package contains organized sequence functionality:
- crud.py: Basic CRUD operations for sequences
- management.py: Sequence management operations
- timezone.py: Timezone-related sequence operations
- validation.py: Sequence validation and testing
"""

from flask import Blueprint

# Create the main sequence blueprint
sequence_bp = Blueprint('sequence', __name__)

# Import all route modules to register them
from . import crud
from . import management
from . import timezone
from . import validation

# Export the blueprint
__all__ = ['sequence_bp']
