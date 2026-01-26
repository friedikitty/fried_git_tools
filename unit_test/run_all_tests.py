#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test runner for all unit tests in the git_sync module.

Run with: python run_all_tests.py
"""

import sys
import os
import unittest
from pathlib import Path

# Add parent directory to path
SCRIPT_DIR = Path(__file__).parent.absolute()
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))


def discover_and_run_tests():
    """Discover and run all tests in the unit_test directory."""
    print("=" * 80)
    print("Git Sync Unit Test Runner")
    print("=" * 80)
    print(f"Test directory: {SCRIPT_DIR}")
    print(f"Parent directory: {PARENT_DIR}")
    print("=" * 80)
    
    # Discover all tests in the current directory
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(SCRIPT_DIR),
        pattern="test_*.py",
        top_level_dir=str(PARENT_DIR)
    )
    
    # Count tests
    test_count = suite.countTestCases()
    print(f"\nDiscovered {test_count} test(s)")
    print("=" * 80)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Total tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n[PASS] All tests passed!")
    else:
        print("\n[FAIL] Some tests failed!")
    
    print("=" * 80)
    
    return result.wasSuccessful()


def main():
    """Main entry point."""
    try:
        success = discover_and_run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
