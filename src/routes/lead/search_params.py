"""
Search parameters and helper functionality.

This module contains endpoints for:
- Getting available search parameters
- Search parameter helpers
- Search parameter validation
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
from src.services.search_parameters_helper import SearchParametersHelper
from src.routes.lead import lead_bp
import logging

logger = logging.getLogger(__name__)


@lead_bp.route('/leads/search-parameters', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_search_parameters():
    """Get available search parameters for LinkedIn Sales Navigator."""
    try:
        helper = SearchParametersHelper()
        
        return jsonify({
            'search_parameters': {
                'keywords': helper.get_keywords(),
                'locations': helper.get_locations(),
                'industries': helper.get_industries(),
                'company_sizes': helper.get_company_sizes(),
                'seniority_levels': helper.get_seniority_levels(),
                'function_types': helper.get_function_types(),
                'connection_degrees': helper.get_connection_degrees()
            },
            'search_templates': {
                'sales_director': {
                    'description': 'Search for Sales Directors and VP Sales',
                    'keywords': ['Sales Director', 'VP Sales', 'Head of Sales'],
                    'seniority_levels': ['Senior', 'Director', 'VP', 'C-Level']
                },
                'tech_engineer': {
                    'description': 'Search for Software Engineers and Developers',
                    'keywords': ['Software Engineer', 'Developer', 'Full Stack'],
                    'function_types': ['Engineering', 'Information Technology']
                },
                'cxo': {
                    'description': 'Search for C-Level executives',
                    'keywords': ['CEO', 'CTO', 'CFO', 'COO'],
                    'seniority_levels': ['C-Level']
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting search parameters: {str(e)}")
        return jsonify({'error': str(e)}), 500


@lead_bp.route('/leads/search-parameters/helper', methods=['GET'])
# @jwt_required()  # Temporarily removed for development
def get_search_parameters_helper():
    """Get search parameters helper with examples and validation."""
    try:
        helper = SearchParametersHelper()
        
        return jsonify({
            'helper_info': {
                'description': 'Search parameters helper for LinkedIn Sales Navigator',
                'usage': 'Use these parameters to build targeted searches',
                'validation': 'All parameters are validated before use'
            },
            'examples': {
                'basic_search': {
                    'keywords': ['Sales Director'],
                    'locations': ['United States'],
                    'industries': ['Technology'],
                    'company_sizes': ['51-200', '201-500']
                },
                'advanced_search': {
                    'keywords': ['VP Sales', 'Head of Sales'],
                    'locations': ['United Kingdom'],
                    'industries': ['Financial Services'],
                    'seniority_levels': ['Senior', 'Director', 'VP'],
                    'function_types': ['Sales']
                }
            },
            'validation_rules': {
                'keywords': 'Must be array of strings, max 10 keywords',
                'locations': 'Must be array of strings, max 5 locations',
                'industries': 'Must be array of strings, max 5 industries',
                'company_sizes': 'Must be array of strings, max 3 sizes',
                'seniority_levels': 'Must be array of strings, max 5 levels',
                'function_types': 'Must be array of strings, max 5 types',
                'connection_degrees': 'Must be array of strings, max 3 degrees'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting search parameters helper: {str(e)}")
        return jsonify({'error': str(e)}), 500
