"""
Sequence engine services package - refactored from the monolithic sequence_engine.py file.

This package contains organized sequence engine functionality:
- core.py: Main sequence engine class and core functionality
- timezone.py: Timezone handling and working day calculations
- message_formatter.py: Message formatting and personalization
- action_executor.py: Connection requests and message sending
- delay_calculator.py: Delay calculations and timing logic
"""

from .core import SequenceEngine, EXAMPLE_SEQUENCE

# Export the main sequence engine class and example sequence
__all__ = ['SequenceEngine', 'EXAMPLE_SEQUENCE']
