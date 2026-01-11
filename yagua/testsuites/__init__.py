"""Yagua - Test Suites Module.

This module provides test suite handlers for different testing frameworks.
Suite handlers are responsible for discovering tests and collecting coverage
information from test projects using framework-specific tools.

Available Handlers
------------------
TestSuiteABC : class
    Abstract base class defining the interface for test suite handlers.
    Extend this class to add support for new testing frameworks.
PytestSuite : class
    Concrete implementation for pytest-based projects.
    Uses pytest's collection API and pytest-cov for coverage.
PytestSuiteSyscall : class
    Alternative pytest implementation using subprocess system calls.
    Uses pytest CLI commands and hash-based temporary files.

Design Pattern
--------------
The test suite handler pattern separates test framework-specific logic from
the core Project management. This allows yagua to support multiple testing
frameworks while keeping the Project API consistent.

Each handler implements three core methods:
- get_tests(): Discover all tests in a project
- get_coverage(): Measure total project coverage
- get_coverage_for_tests(): Measure coverage for specific tests

Extending Support
-----------------
To add support for a new testing framework (e.g., unittest, nose):

1. Create a new class that inherits from TestSuiteABC
2. Implement all three abstract methods
3. Return data in the format specified by TestSuiteABC
4. Export the new class from this module

Example
-------
>>> from yagua.testsuites import PytestSuite
>>> suite = PytestSuite()
>>> tests, cmd, stdout, stderr, data = suite.get_tests("/path/to/project")
>>> print(f"Found {len(tests)} tests")
"""

from .abc import TestSuiteABC
from .pytest_suite import PytestSuite
from .pytest_suite_syscall import PytestSuiteSyscall

__all__ = ["TestSuiteABC", "PytestSuite", "PytestSuiteSyscall"]
