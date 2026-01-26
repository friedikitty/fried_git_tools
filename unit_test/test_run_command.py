#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for run_command module.

Run with: python -m pytest test_run_command.py
Or: python test_run_command.py
"""

import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path to import run_command
SCRIPT_DIR = Path(__file__).parent.absolute()
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from run_command import (
    run_command,
    run_command_and_get_return_info,
    ConsoleCommandLogger,
    OutputCaptureLogger,
)


class TestConsoleCommandLogger(unittest.TestCase):
    """Test cases for ConsoleCommandLogger class."""

    def test_logger_initialization(self):
        """Test logger can be initialized with default and custom prefix."""
        logger1 = ConsoleCommandLogger()
        self.assertEqual(logger1.prefix, "[CMD]")
        
        logger2 = ConsoleCommandLogger(prefix="[TEST]")
        self.assertEqual(logger2.prefix, "[TEST]")

    def test_logger_info(self):
        """Test info logging (output to stdout)."""
        logger = ConsoleCommandLogger(prefix="[INFO]")
        # This will print to stdout, just verify it doesn't raise
        try:
            logger.info("Test message")
        except Exception as e:
            self.fail(f"info() raised {e}")

    def test_logger_error(self):
        """Test error logging (output to stdout)."""
        logger = ConsoleCommandLogger(prefix="[ERR]")
        # This will print to stdout, just verify it doesn't raise
        try:
            logger.error("Test error")
        except Exception as e:
            self.fail(f"error() raised {e}")


class TestOutputCaptureLogger(unittest.TestCase):
    """Test cases for OutputCaptureLogger class."""

    def test_capture_without_original_logger(self):
        """Test capture logger works without an original logger."""
        capture_logger = OutputCaptureLogger(None)
        capture_logger.info("Info message")
        capture_logger.error("Error message")
        
        output = capture_logger.get_output()
        self.assertIn("Info message", output)
        self.assertIn("Error message", output)

    def test_capture_with_original_logger(self):
        """Test capture logger forwards to original logger."""
        original_logger = ConsoleCommandLogger(prefix="[ORIG]")
        capture_logger = OutputCaptureLogger(original_logger)
        
        capture_logger.info("Test info")
        capture_logger.error("Test error")
        
        output = capture_logger.get_output()
        self.assertEqual(output, "Test info\nTest error")

    def test_captured_output_order(self):
        """Test captured output maintains order."""
        capture_logger = OutputCaptureLogger(None)
        
        capture_logger.info("First")
        capture_logger.error("Second")
        capture_logger.info("Third")
        
        output = capture_logger.get_output()
        self.assertEqual(output, "First\nSecond\nThird")


class TestRunCommand(unittest.TestCase):
    """Test cases for run_command function."""

    def test_simple_command_success(self):
        """Test running a simple successful command."""
        if sys.platform == "win32":
            result = run_command(["cmd", "/c", "echo", "test"], shell=False)
        else:
            result = run_command(["echo", "test"], shell=False)
        
        self.assertEqual(result, 0)

    def test_simple_command_with_shell(self):
        """Test running command with shell=True."""
        if sys.platform == "win32":
            result = run_command("echo test", shell=True)
        else:
            result = run_command("echo test", shell=True)
        
        self.assertEqual(result, 0)

    def test_command_failure(self):
        """Test running a command that fails."""
        if sys.platform == "win32":
            # Use a command that will fail
            result = run_command(["cmd", "/c", "exit", "1"], shell=False)
        else:
            result = run_command(["false"], shell=False)
        
        self.assertNotEqual(result, 0)

    def test_command_with_cwd(self):
        """Test running command in specific directory."""
        if sys.platform == "win32":
            result = run_command(["cmd", "/c", "cd"], cwd=PARENT_DIR, shell=False)
        else:
            result = run_command(["pwd"], cwd=PARENT_DIR, shell=False)
        
        self.assertEqual(result, 0)

    def test_command_with_logger(self):
        """Test running command with logger."""
        capture_logger = OutputCaptureLogger(None)
        
        if sys.platform == "win32":
            result = run_command(
                ["cmd", "/c", "echo", "logged"],
                shell=False,
                logger=capture_logger
            )
        else:
            result = run_command(
                ["echo", "logged"],
                shell=False,
                logger=capture_logger
            )
        
        self.assertEqual(result, 0)
        output = capture_logger.get_output()
        self.assertIn("Return:", output)

    def test_nonexistent_command(self):
        """Test running a command that doesn't exist."""
        result = run_command(
            ["nonexistent_command_12345"], 
            shell=False
        )
        self.assertEqual(result, -1)

    def test_command_with_timeout(self):
        """Test command timeout handling."""
        if sys.platform == "win32":
            # Use timeout command on Windows (sleep for 2 seconds with 0.1s timeout)
            result = run_command(
                ["cmd", "/c", "timeout", "/t", "2", "/nobreak"],
                shell=False,
                timeout=0.1
            )
        else:
            # Use sleep on Unix (sleep for 2 seconds with 0.1s timeout)
            result = run_command(
                ["sleep", "2"],
                shell=False,
                timeout=0.1
            )
        
        # Should fail due to timeout
        self.assertEqual(result, -1)


class TestRunCommandAndGetReturnInfo(unittest.TestCase):
    """Test cases for run_command_and_get_return_info function."""

    def test_get_output(self):
        """Test getting command output."""
        if sys.platform == "win32":
            output = run_command_and_get_return_info(
                "echo Hello",
                shell=True
            )
        else:
            output = run_command_and_get_return_info(
                "echo Hello",
                shell=True
            )
        
        self.assertIn("Hello", output)

    def test_get_output_with_cwd(self):
        """Test getting command output with cwd."""
        if sys.platform == "win32":
            output = run_command_and_get_return_info(
                "cd",
                cwd=PARENT_DIR,
                shell=True
            )
        else:
            output = run_command_and_get_return_info(
                "pwd",
                cwd=PARENT_DIR,
                shell=True
            )
        
        self.assertIsNotNone(output)
        self.assertIsInstance(output, str)

    def test_command_failure_raises_exception(self):
        """Test that failed command raises exception."""
        with self.assertRaises(Exception):
            if sys.platform == "win32":
                run_command_and_get_return_info(
                    "exit 1",
                    shell=True
                )
            else:
                run_command_and_get_return_info(
                    "false",
                    shell=True
                )


class TestRunCommandStreaming(unittest.TestCase):
    """Test cases for streaming output functionality."""

    def test_streaming_simple_command(self):
        """Test streaming output for simple command."""
        if sys.platform == "win32":
            result = run_command(
                ["cmd", "/c", "echo", "streaming"],
                shell=False,
                stream_output=True,
                stderr_to_stdout=True
            )
        else:
            result = run_command(
                ["echo", "streaming"],
                shell=False,
                stream_output=True,
                stderr_to_stdout=True
            )
        
        self.assertEqual(result, 0)

    def test_streaming_with_logger(self):
        """Test streaming output with logger."""
        capture_logger = OutputCaptureLogger(None)
        
        if sys.platform == "win32":
            result = run_command(
                ["cmd", "/c", "echo", "test"],
                shell=False,
                stream_output=True,
                stderr_to_stdout=True,
                logger=capture_logger
            )
        else:
            result = run_command(
                ["echo", "test"],
                shell=False,
                stream_output=True,
                stderr_to_stdout=True,
                logger=capture_logger
            )
        
        self.assertEqual(result, 0)


class TestRunCommandErrorRegex(unittest.TestCase):
    """Test cases for error regex detection."""

    def test_error_regex_detection(self):
        """Test that error regex correctly identifies error lines."""
        capture_logger = OutputCaptureLogger(None)
        
        if sys.platform == "win32":
            # Echo a line with "error" in it
            result = run_command(
                ["cmd", "/c", "echo", "This is an error message"],
                shell=False,
                error_regex=r".*error.*",
                logger=capture_logger
            )
        else:
            result = run_command(
                ["echo", "This is an error message"],
                shell=False,
                error_regex=r".*error.*",
                logger=capture_logger
            )
        
        self.assertEqual(result, 0)


def run_tests():
    """Run all unit tests."""
    print("=" * 80)
    print("Running Unit Tests for run_command module")
    print("=" * 80)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestConsoleCommandLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestOutputCaptureLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestRunCommand))
    suite.addTests(loader.loadTestsFromTestCase(TestRunCommandAndGetReturnInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestRunCommandStreaming))
    suite.addTests(loader.loadTestsFromTestCase(TestRunCommandErrorRegex))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
