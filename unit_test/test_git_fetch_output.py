#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify git fetch output streaming works correctly.
"""

import sys
import os
import tempfile

# Add parent directory to path to import run_command
sys.path.insert(0, os.path.dirname(__file__))
from run_command import run_command

def test_git_fetch_streaming():
    """Test that git fetch shows real-time output."""
    print("="*80)
    print("Testing git fetch with real-time output streaming")
    print("="*80)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\nCreated temp directory: {temp_dir}")
        
        # Initialize a bare git repo
        print("\n1. Initializing bare repository...")
        result = run_command("git init --bare", cwd=temp_dir)
        if result != 0:
            print("Failed to initialize repository")
            return False
        
        # Add a remote (using a public repository for testing)
        print("\n2. Adding remote...")
        test_remote = "https://github.com/git/git.git"
        result = run_command(f"git remote add origin {test_remote}", cwd=temp_dir)
        if result != 0:
            print("Failed to add remote")
            return False
        
        # Test fetch with streaming output
        print("\n3. Testing git fetch with streaming output...")
        print("You should see progress output in real-time below:")
        print("-" * 80)
        
        result = run_command(
            ["git", "fetch", "--progress", "origin", "master"],
            cwd=temp_dir,
            stream_output=True,
            stderr_to_stdout=True,
        )
        
        print("-" * 80)
        if result == 0:
            print("\n[SUCCESS] Git fetch completed with real-time output!")
            return True
        else:
            print("\n[FAILED] Git fetch failed")
            return False

if __name__ == "__main__":
    try:
        success = test_git_fetch_streaming()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
