#!/usr/bin/env python3
# filepath: /home/friedjof/Dokumente/repositories/VibeBot/discord-bot/tests/run_all_tests.py
"""
Test runner for the 1337 Game role system tests.
"""
import unittest
import sys
import os
import time
from io import StringIO

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_test_suite():
    """Run all test suites and generate a report."""
    print("=" * 80)
    print("1337 GAME ROLE SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()
    
    # Test modules to run
    test_modules = [
        'test_role_system',
        'test_1337_game_integration', 
        'test_database_operations',
        'test_performance'
    ]
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    
    start_time = time.time()
    
    for module_name in test_modules:
        print(f"Running {module_name}...")
        print("-" * 40)
        
        # Import and run the test module
        try:
            # Capture test output
            test_output = StringIO()
            
            # Load the test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            
            # Run the tests
            runner = unittest.TextTestRunner(
                stream=test_output,
                verbosity=2,
                buffer=True
            )
            
            result = runner.run(suite)
            
            # Print results
            output = test_output.getvalue()
            print(output)
            
            # Update totals
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            total_skipped += len(result.skipped)
            
            # Print module summary
            print(f"Module {module_name} summary:")
            print(f"  Tests run: {result.testsRun}")
            print(f"  Failures: {len(result.failures)}")
            print(f"  Errors: {len(result.errors)}")
            print(f"  Skipped: {len(result.skipped)}")
            
            if result.failures:
                print("  Failures:")
                for test, traceback in result.failures:
                    print(f"    - {test}: {traceback.split(chr(10))[0]}")
            
            if result.errors:
                print("  Errors:")
                for test, traceback in result.errors:
                    print(f"    - {test}: {traceback.split(chr(10))[0]}")
            
            print()
            
        except Exception as e:
            print(f"ERROR: Could not run {module_name}: {e}")
            total_errors += 1
            print()
    
    elapsed_time = time.time() - start_time
    
    # Print overall summary
    print("=" * 80)
    print("OVERALL TEST RESULTS")
    print("=" * 80)
    print(f"Total test modules: {len(test_modules)}")
    print(f"Total tests run: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Total errors: {total_errors}")
    print(f"Total skipped: {total_skipped}")
    print(f"Success rate: {((total_tests - total_failures - total_errors) / max(total_tests, 1)) * 100:.1f}%")
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print()
    
    # Overall result
    if total_failures == 0 and total_errors == 0:
        print("🎉 ALL TESTS PASSED! 🎉")
        return True
    else:
        print("❌ SOME TESTS FAILED ❌")
        return False


def run_specific_test_category(category):
    """Run tests for a specific category."""
    category_mapping = {
        'unit': ['test_role_system', 'test_database_operations'],
        'integration': ['test_1337_game_integration'],
        'performance': ['test_performance'],
        'all': ['test_role_system', 'test_1337_game_integration', 'test_database_operations', 'test_performance']
    }
    
    if category not in category_mapping:
        print(f"Unknown category: {category}")
        print(f"Available categories: {', '.join(category_mapping.keys())}")
        return False
    
    print(f"Running {category} tests...")
    test_modules = category_mapping[category]
    
    for module_name in test_modules:
        print(f"\nRunning {module_name}...")
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            
            if result.failures or result.errors:
                return False
        except Exception as e:
            print(f"Error running {module_name}: {e}")
            return False
    
    return True


def run_coverage_analysis():
    """Run tests with coverage analysis if coverage.py is available."""
    try:
        import coverage
        
        print("Running tests with coverage analysis...")
        
        # Start coverage
        cov = coverage.Coverage()
        cov.start()
        
        # Run tests
        success = run_test_suite()
        
        # Stop coverage and generate report
        cov.stop()
        cov.save()
        
        print("\nCoverage Report:")
        print("-" * 40)
        cov.report(show_missing=True)
        
        # Generate HTML report
        try:
            cov.html_report(directory='htmlcov')
            print("\nHTML coverage report generated in 'htmlcov' directory")
        except:
            pass
        
        return success
        
    except ImportError:
        print("Coverage.py not available. Running tests without coverage analysis.")
        return run_test_suite()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'coverage':
            success = run_coverage_analysis()
        elif command in ['unit', 'integration', 'performance', 'all']:
            success = run_specific_test_category(command)
        else:
            print("Usage:")
            print("  python run_all_tests.py [category|coverage]")
            print("  Categories: unit, integration, performance, all")
            print("  coverage: Run with coverage analysis (requires coverage.py)")
            sys.exit(1)
    else:
        success = run_test_suite()
    
    sys.exit(0 if success else 1)
