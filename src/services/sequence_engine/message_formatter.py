"""
Message formatting and personalization functionality.

This module contains functionality for:
- Message personalization
- Placeholder replacement
- Lead data formatting
- Message validation
"""

import logging
import re
from typing import Dict, Any
from src.models import Lead

logger = logging.getLogger(__name__)


def _format_message(self, message: str, lead: Lead) -> str:
    """Format a message by replacing placeholders with lead data."""
    try:
        # CRITICAL FIX: Validate lead object and refresh from database
        if not lead or not hasattr(lead, 'id'):
            logger.error("Invalid lead object passed to _format_message")
            return message
        
        # Always refresh lead data to ensure we have the latest information
        try:
            db.session.refresh(lead)
        except Exception as refresh_error:
            logger.error(f"Failed to refresh lead {lead.id} in _format_message: {str(refresh_error)}")
            return message
        
        logger.info(f"=== PERSONALIZATION DEBUG START ===")
        logger.info(f"Lead ID: {lead.id}")
        logger.info(f"Lead first_name: '{lead.first_name}'")
        logger.info(f"Lead last_name: '{lead.last_name}'")
        logger.info(f"Lead company_name: '{lead.company_name}'")
        logger.info(f"Lead status: '{lead.status}'")
        logger.info(f"Lead current_step: {lead.current_step}")
        logger.info(f"Original message: '{message}'")
        logger.info(f"=== PERSONALIZATION DEBUG END ===")
        
        if not message:
            return ""
        
        # Define placeholders and their corresponding lead attributes
        placeholders = {
            '{{first_name}}': lead.first_name or 'there',
            '{{last_name}}': lead.last_name or '',
            '{{full_name}}': f"{lead.first_name or ''} {lead.last_name or ''}".strip() or 'there',
            '{{company}}': lead.company_name or 'your company',
            '{{company_name}}': lead.company_name or 'your company',
            '{{position}}': getattr(lead, 'position', '') or 'your role',
            '{{title}}': getattr(lead, 'title', '') or 'your role',
            '{{location}}': getattr(lead, 'location', '') or 'your area',
            '{{industry}}': getattr(lead, 'industry', '') or 'your industry',
            '{{campaign_name}}': getattr(lead, 'campaign_name', '') or 'our campaign'
        }
        
        # Replace placeholders
        formatted_message = message
        for placeholder, value in placeholders.items():
            if placeholder in formatted_message:
                formatted_message = formatted_message.replace(placeholder, str(value))
                logger.info(f"Replaced {placeholder} with '{value}'")
        
        # CRITICAL SAFETY CHECK: Verify the message makes sense
        if '{{first_name}}' in formatted_message:
            logger.error(f"CRITICAL ERROR: {{first_name}} placeholder still in message after formatting!")
            logger.error(f"Lead ID: {lead.id}, Lead Name: {lead.first_name} {lead.last_name}")
            logger.error(f"Original message: {message}")
            logger.error(f"Formatted message: {formatted_message}")
            # Return a safe fallback message
            return f"Hi there, {message.replace('{{first_name}}', 'there')}"
        
        # Handle case where no first name is available
        if '{{first_name}}' in formatted_message and not lead.first_name:
            formatted_message = formatted_message.replace('{{first_name}}', 'there')
            logger.info("Replaced {{first_name}} with 'there' (fallback)")
        
        # Handle case where no company name is available
        if '{{company}}' in formatted_message and not lead.company_name:
            formatted_message = formatted_message.replace('{{company}}', 'your company')
            logger.info("Replaced {{company}} with 'your company' (fallback)")
        
        if '{{company_name}}' in formatted_message and not lead.company_name:
            formatted_message = formatted_message.replace('{{company_name}}', 'your company')
            logger.info("Replaced {{company_name}} with 'your company' (fallback)")
        
        logger.info(f"Final formatted message: '{formatted_message}'")
        return formatted_message
        
    except Exception as e:
        logger.error(f"Error formatting message: {str(e)}")
        return message  # Return original message if formatting fails


def _validate_message(self, message: str) -> Dict[str, Any]:
    """Validate a message for common issues."""
    try:
        errors = []
        warnings = []
        
        if not message:
            errors.append("Message cannot be empty")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Check message length
        if len(message) > 1000:
            warnings.append("Message is very long (>1000 characters)")
        
        if len(message) < 10:
            warnings.append("Message is very short (<10 characters)")
        
        # Check for personalization placeholders
        placeholder_pattern = r'\{\{[^}]+\}\}'
        placeholders = re.findall(placeholder_pattern, message)
        
        if not placeholders:
            warnings.append("No personalization placeholders found")
        else:
            # Check for common placeholders
            common_placeholders = ['{{first_name}}', '{{company}}', '{{company_name}}']
            found_common = [p for p in placeholders if p in common_placeholders]
            
            if not found_common:
                warnings.append("No common personalization placeholders found")
        
        # Check for potential issues
        if '{{' in message and '}}' not in message:
            errors.append("Unclosed placeholder bracket")
        
        if '}}' in message and '{{' not in message:
            errors.append("Unopened placeholder bracket")
        
        # Check for excessive punctuation
        if message.count('!') > 3:
            warnings.append("Excessive exclamation marks")
        
        if message.count('?') > 3:
            warnings.append("Excessive question marks")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'placeholders': placeholders
        }
        
    except Exception as e:
        logger.error(f"Error validating message: {str(e)}")
        return {
            'valid': False,
            'errors': [str(e)],
            'warnings': [],
            'placeholders': []
        }


def _get_available_placeholders(self) -> Dict[str, str]:
    """Get a list of available placeholders and their descriptions."""
    return {
        '{{first_name}}': 'Lead\'s first name',
        '{{last_name}}': 'Lead\'s last name',
        '{{full_name}}': 'Lead\'s full name',
        '{{company}}': 'Lead\'s company name',
        '{{company_name}}': 'Lead\'s company name (alternative)',
        '{{position}}': 'Lead\'s position/title',
        '{{title}}': 'Lead\'s title/role',
        '{{location}}': 'Lead\'s location',
        '{{industry}}': 'Lead\'s industry',
        '{{campaign_name}}': 'Campaign name'
    }


def _preview_message(self, message: str, lead_data: Dict[str, Any]) -> str:
    """Preview a message with sample lead data."""
    try:
        # Create a mock lead object for preview
        class MockLead:
            def __init__(self, data):
                self.first_name = data.get('first_name', 'John')
                self.last_name = data.get('last_name', 'Doe')
                self.company_name = data.get('company_name', 'Sample Company')
                self.position = data.get('position', 'Manager')
                self.location = data.get('location', 'New York')
                self.industry = data.get('industry', 'Technology')
        
        mock_lead = MockLead(lead_data)
        return self._format_message(message, mock_lead)
        
    except Exception as e:
        logger.error(f"Error previewing message: {str(e)}")
        return message
