"""
Testing package for LinkedIn Automation API.

This package contains:
- Unit tests for individual components
- Integration tests for API endpoints
- Test utilities and fixtures
- Database test setup and teardown
"""

import os
import sys
import tempfile
import shutil
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Test configuration
TEST_CONFIG = {
    'TESTING': True,
    'DATABASE_URL': 'sqlite:///:memory:',  # Use in-memory SQLite for tests
    'SECRET_KEY': 'test-secret-key',
    'JWT_SECRET_KEY': 'test-jwt-secret',
    'UNIPILE_API_KEY': 'test-unipile-key',
    'UNIPILE_API_BASE_URL': 'https://test-api.unipile.com',
    'RESEND_API_KEY': 'test-resend-key',
    'NOTIFY_EMAIL_FROM': 'test@example.com',
    'NOTIFY_EMAIL_TO': 'test@example.com',
    'CORS_ORIGINS': ['http://localhost:3000'],
    'MAX_CONNECTIONS_PER_DAY': '25',
    'MAX_MESSAGES_PER_DAY': '100',
    'MIN_DELAY_BETWEEN_ACTIONS': '300',
    'MAX_DELAY_BETWEEN_ACTIONS': '1800',
    'WORKING_HOURS_START': '9',
    'WORKING_HOURS_END': '17',
    'LOG_LEVEL': 'DEBUG'
}
