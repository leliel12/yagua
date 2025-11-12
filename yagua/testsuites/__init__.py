"""
Yagua - Test Suites.

This module provides test suite handlers for different testing frameworks.
"""

from .abc import TestSuiteABC
from .pytest_suite import PytestSuite

__all__ = ["TestSuiteABC", "PytestSuite"]
