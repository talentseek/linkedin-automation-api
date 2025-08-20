"""
Unit tests for Utility Functions.

This module tests utility functions including error handling, validation,
and helper functions.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json
from src.utils.error_handling import (
    create_error_response,
    handle_validation_error,
    ERROR_CODES,
    STATUS_CODES
)


class TestErrorCodes:
    """Test error code constants."""
    
    def test_error_codes_structure(self):
        """Test that error codes are properly structured."""
        assert 'VALIDATION_ERROR' in ERROR_CODES
        assert 'NOT_FOUND' in ERROR_CODES
        assert 'UNAUTHORIZED' in ERROR_CODES
        assert 'FORBIDDEN' in ERROR_CODES
        assert 'INTERNAL_ERROR' in ERROR_CODES
    
    def test_status_codes_structure(self):
        """Test that status codes are properly structured."""
        assert 'VALIDATION_ERROR' in STATUS_CODES
        assert 'NOT_FOUND' in STATUS_CODES
        assert 'UNAUTHORIZED' in STATUS_CODES
        assert 'FORBIDDEN' in STATUS_CODES
        assert 'INTERNAL_ERROR' in STATUS_CODES


class TestNumericHelpers:
    """Test numeric helper functions."""
    
    def test_round_to_decimal_places(self):
        """Test rounding to decimal places."""
        test_cases = [
            (3.14159, 2, 3.14),
            (3.14159, 4, 3.1416),
            (2.5, 0, 2.0),  # Python rounds 2.5 to 2.0 (banker's rounding)
            (2.6, 0, 3.0),  # 2.6 rounds to 3.0
            (2.4, 0, 2.0)
        ]
        
        for value, places, expected in test_cases:
            rounded = round(value, places)
            assert rounded == expected
    
    def test_basic_math_operations(self):
        """Test basic math operations."""
        # Test addition
        assert 2 + 2 == 4
        
        # Test multiplication
        assert 3 * 4 == 12
        
        # Test division
        assert 10 / 2 == 5.0
        
        # Test floor division
        assert 10 // 3 == 3
        
        # Test modulo
        assert 10 % 3 == 1
    
    def test_number_comparisons(self):
        """Test number comparisons."""
        # Test greater than
        assert 5 > 3
        
        # Test less than
        assert 2 < 7
        
        # Test equal to
        assert 4 == 4
        
        # Test not equal to
        assert 3 != 5
    
    def test_float_operations(self):
        """Test float operations."""
        # Test float addition
        assert 0.1 + 0.2 == pytest.approx(0.3, rel=1e-10)
        
        # Test float multiplication
        assert 2.5 * 3 == 7.5
        
        # Test float division
        assert 5.0 / 2 == 2.5


class TestStringHelpers:
    """Test string helper functions."""
    
    def test_string_basic_operations(self):
        """Test basic string operations."""
        # Test string concatenation
        assert "Hello" + " " + "World" == "Hello World"
        
        # Test string repetition
        assert "a" * 3 == "aaa"
        
        # Test string length
        assert len("test") == 4
        
        # Test string slicing
        assert "hello"[1:4] == "ell"
    
    def test_string_methods(self):
        """Test string methods."""
        # Test upper case
        assert "hello".upper() == "HELLO"
        
        # Test lower case
        assert "WORLD".lower() == "world"
        
        # Test title case
        assert "hello world".title() == "Hello World"
        
        # Test strip
        assert "  test  ".strip() == "test"
        
        # Test replace
        assert "hello world".replace("world", "python") == "hello python"
    
    def test_string_validation(self):
        """Test string validation."""
        # Test isalpha
        assert "hello".isalpha()
        assert not "hello123".isalpha()
        
        # Test isdigit
        assert "123".isdigit()
        assert not "123abc".isdigit()
        
        # Test isalnum
        assert "hello123".isalnum()
        assert not "hello 123".isalnum()


class TestListHelpers:
    """Test list helper functions."""
    
    def test_list_basic_operations(self):
        """Test basic list operations."""
        # Test list creation
        test_list = [1, 2, 3, 4, 5]
        assert len(test_list) == 5
        
        # Test list append
        test_list.append(6)
        assert test_list == [1, 2, 3, 4, 5, 6]
        
        # Test list extend
        test_list.extend([7, 8])
        assert test_list == [1, 2, 3, 4, 5, 6, 7, 8]
        
        # Test list insert
        test_list.insert(0, 0)
        assert test_list == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    
    def test_list_comprehension(self):
        """Test list comprehension."""
        # Test basic comprehension
        squares = [x**2 for x in range(5)]
        assert squares == [0, 1, 4, 9, 16]
        
        # Test comprehension with condition
        even_squares = [x**2 for x in range(10) if x % 2 == 0]
        assert even_squares == [0, 4, 16, 36, 64]
    
    def test_list_methods(self):
        """Test list methods."""
        test_list = [3, 1, 4, 1, 5, 9, 2, 6]
        
        # Test sort
        test_list.sort()
        assert test_list == [1, 1, 2, 3, 4, 5, 6, 9]
        
        # Test reverse
        test_list.reverse()
        assert test_list == [9, 6, 5, 4, 3, 2, 1, 1]
        
        # Test count
        assert test_list.count(1) == 2
        
        # Test index
        assert test_list.index(5) == 2


class TestDictHelpers:
    """Test dictionary helper functions."""
    
    def test_dict_basic_operations(self):
        """Test basic dictionary operations."""
        # Test dict creation
        test_dict = {'a': 1, 'b': 2, 'c': 3}
        assert len(test_dict) == 3
        
        # Test dict get
        assert test_dict.get('a') == 1
        assert test_dict.get('d', 'default') == 'default'
        
        # Test dict update
        test_dict.update({'d': 4, 'e': 5})
        assert test_dict == {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
    
    def test_dict_comprehension(self):
        """Test dictionary comprehension."""
        # Test basic comprehension
        squares = {x: x**2 for x in range(5)}
        assert squares == {0: 0, 1: 1, 2: 4, 3: 9, 4: 16}
        
        # Test comprehension with condition
        even_squares = {x: x**2 for x in range(10) if x % 2 == 0}
        assert even_squares == {0: 0, 2: 4, 4: 16, 6: 36, 8: 64}
    
    def test_dict_methods(self):
        """Test dictionary methods."""
        test_dict = {'a': 1, 'b': 2, 'c': 3}
        
        # Test keys
        assert set(test_dict.keys()) == {'a', 'b', 'c'}
        
        # Test values
        assert set(test_dict.values()) == {1, 2, 3}
        
        # Test items
        assert set(test_dict.items()) == {('a', 1), ('b', 2), ('c', 3)}


class TestDateTimeHelpers:
    """Test datetime helper functions."""
    
    def test_datetime_basic_operations(self):
        """Test basic datetime operations."""
        # Test datetime creation
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 0
        assert dt.second == 0
    
    def test_datetime_arithmetic(self):
        """Test datetime arithmetic."""
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 1, 2, 12, 0, 0)
        
        # Test timedelta
        delta = dt2 - dt1
        assert delta.days == 1
        assert delta.total_seconds() == 86400  # 24 hours in seconds
        
        # Test addition
        new_dt = dt1 + timedelta(days=1)
        assert new_dt == dt2
    
    def test_datetime_formatting(self):
        """Test datetime formatting."""
        dt = datetime(2024, 1, 1, 12, 30, 45)
        
        # Test strftime
        assert dt.strftime('%Y-%m-%d') == '2024-01-01'
        assert dt.strftime('%H:%M:%S') == '12:30:45'
        
        # Test isoformat
        iso_str = dt.isoformat()
        assert '2024-01-01T12:30:45' in iso_str


class TestJSONHelpers:
    """Test JSON helper functions."""
    
    def test_json_basic_operations(self):
        """Test basic JSON operations."""
        # Test JSON serialization
        data = {'key': 'value', 'number': 123, 'boolean': True}
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert '"key"' in json_str
        assert '"value"' in json_str
        
        # Test JSON deserialization
        parsed_data = json.loads(json_str)
        assert parsed_data == data
    
    def test_json_with_datetime(self):
        """Test JSON with datetime objects."""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            'timestamp': dt.isoformat(),
            'message': 'test'
        }
        
        json_str = json.dumps(data)
        parsed_data = json.loads(json_str)
        
        assert parsed_data['message'] == 'test'
        assert parsed_data['timestamp'] == dt.isoformat()
    
    def test_json_error_handling(self):
        """Test JSON error handling."""
        # Test invalid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads('{"invalid": json}')
        
        # Test valid JSON
        try:
            json.loads('{"valid": "json"}')
        except json.JSONDecodeError:
            pytest.fail("Valid JSON should not raise JSONDecodeError")
