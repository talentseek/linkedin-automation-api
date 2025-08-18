#!/usr/bin/env python3
"""
Test runner script for LinkedIn Automation API.

This script provides easy ways to run different types of tests:
- All tests
- Unit tests only
- Integration tests only
- With coverage reporting
"""

import sys
import subprocess
import argparse
import os

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run tests for LinkedIn Automation API')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--coverage', action='store_true', help='Run tests with coverage reporting')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--fast', action='store_true', help='Run only fast tests (skip slow/external)')
    
    args = parser.parse_args()
    
    # Set up environment
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    if args.verbose:
        cmd.append('-v')
    
    if args.coverage:
        cmd.extend([
            '--cov=src',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-fail-under=80'
        ])
    
    if args.unit:
        cmd.append('-m unit')
        description = "Unit Tests"
    elif args.integration:
        cmd.append('-m integration')
        description = "Integration Tests"
    elif args.fast:
        cmd.extend(['-m', 'not slow and not external'])
        description = "Fast Tests (excluding slow/external)"
    else:
        description = "All Tests"
    
    # Run the tests
    success = run_command(cmd, description)
    
    if success:
        print(f"\n🎉 All tests passed!")
        if args.coverage:
            print(f"📊 Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
