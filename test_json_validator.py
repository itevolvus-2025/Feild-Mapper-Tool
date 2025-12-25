"""
Test script for JSON Validator
Demonstrates how to use the JSON validator programmatically
"""

import os
import json
from json_validator import JSONValidator


def create_test_files():
    """Create test JSON files for validation"""
    test_dir = "test_json_files"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # Valid JSON file
    valid_data = {
        "name": "John Doe",
        "age": 30,
        "email": "john@example.com",
        "address": {
            "street": "123 Main St",
            "city": "New York",
            "zip": "10001"
        },
        "hobbies": ["reading", "coding", "hiking"]
    }
    with open(os.path.join(test_dir, "valid.json"), "w") as f:
        json.dump(valid_data, f, indent=2)
    
    # JSON with warnings (deep nesting)
    deep_nested = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "level5": {
                            "level6": {
                                "level7": {
                                    "level8": {
                                        "level9": {
                                            "level10": {
                                                "level11": {
                                                    "data": "very deep"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    with open(os.path.join(test_dir, "deep_nested.json"), "w") as f:
        json.dump(deep_nested, f, indent=2)
    
    # JSON with null values (valid JSON, should not trigger warnings)
    with_nulls = {
        "field1": "value1",
        "field2": None,
        "field3": {
            "nested": None
        }
    }
    with open(os.path.join(test_dir, "with_nulls.json"), "w") as f:
        json.dump(with_nulls, f, indent=2)
    
    # Invalid JSON (syntax error)
    with open(os.path.join(test_dir, "invalid_syntax.json"), "w") as f:
        f.write('{\n  "name": "John",\n  "age": 30,\n}')  # Trailing comma
    
    # Empty JSON file
    with open(os.path.join(test_dir, "empty.json"), "w") as f:
        f.write("")
    
    # Array with mixed types
    mixed_array = {
        "items": [
            {"type": "A", "value": 1},
            {"type": "B", "value": 2},
            "string_item",  # Different type
            123  # Different type
        ]
    }
    with open(os.path.join(test_dir, "mixed_array.json"), "w") as f:
        json.dump(mixed_array, f, indent=2)
    
    # Minified JSON (single line, no indentation - perfectly valid)
    minified_data = {"name": "John", "age": 30, "city": "New York", "active": True}
    with open(os.path.join(test_dir, "minified.json"), "w") as f:
        json.dump(minified_data, f)  # No indent = minified
    
    return test_dir


def test_single_file_validation():
    """Test validating a single file"""
    print("\n" + "="*80)
    print("TEST 1: Single File Validation")
    print("="*80)
    
    validator = JSONValidator()
    
    # Test valid file
    result = validator.validate_file("test_json_files/valid.json")
    print(f"\nFile: valid.json")
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Info: {result['info']}")
    
    # Test invalid file
    result = validator.validate_file("test_json_files/invalid_syntax.json")
    print(f"\nFile: invalid_syntax.json")
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    if result.get('info', {}).get('suggestions'):
        print(f"Suggestions: {result['info']['suggestions']}")


def test_batch_validation():
    """Test validating multiple files"""
    print("\n" + "="*80)
    print("TEST 2: Batch Validation")
    print("="*80)
    
    validator = JSONValidator()
    
    # Get all test files
    test_files = [
        os.path.join("test_json_files", f)
        for f in os.listdir("test_json_files")
        if f.endswith(".json")
    ]
    
    # Validate all files
    results = validator.validate_batch(test_files)
    
    print(f"\nTotal Files: {results['total_files']}")
    print(f"Valid Files: {results['valid_files']}")
    print(f"Invalid Files: {results['invalid_files']}")
    print(f"Files with Warnings: {results['files_with_warnings']}")
    
    # Show details for each file
    print("\nDetailed Results:")
    for detail in results['details']:
        filename = os.path.basename(detail['file'])
        status = "[VALID]" if detail['valid'] else "[INVALID]"
        print(f"\n  {filename}: {status}")
        
        if detail['errors']:
            print(f"    Errors: {len(detail['errors'])}")
            for error in detail['errors'][:2]:  # Show first 2 errors
                print(f"      - {error}")
        
        if detail['warnings']:
            print(f"    Warnings: {len(detail['warnings'])}")
            for warning in detail['warnings'][:2]:  # Show first 2 warnings
                print(f"      - {warning}")


def test_report_generation():
    """Test generating a validation report"""
    print("\n" + "="*80)
    print("TEST 3: Report Generation")
    print("="*80)
    
    validator = JSONValidator()
    
    # Get all test files
    test_files = [
        os.path.join("test_json_files", f)
        for f in os.listdir("test_json_files")
        if f.endswith(".json")
    ]
    
    # Validate and generate report
    results = validator.validate_batch(test_files)
    report_path = "test_validation_report.txt"
    report = validator.generate_report(results, report_path)
    
    print(f"\nReport generated: {report_path}")
    print("\nReport Preview:")
    print("-" * 80)
    # Show first 40 lines of report
    lines = report.split('\n')
    for line in lines[:40]:
        print(line)
    if len(lines) > 40:
        print(f"\n... ({len(lines) - 40} more lines)")


def test_schema_validation():
    """Test schema validation (if jsonschema is available)"""
    print("\n" + "="*80)
    print("TEST 4: Schema Validation")
    print("="*80)
    
    validator = JSONValidator()
    
    # Define a simple schema
    schema = {
        "type": "object",
        "required": ["name", "age"],
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number"},
            "email": {"type": "string"}
        }
    }
    
    # Test with schema
    result = validator.validate_file("test_json_files/valid.json", schema)
    
    print(f"\nFile: valid.json")
    print(f"Schema Validation: {result['valid']}")
    if 'schema_validation' in result.get('info', {}):
        print(f"Schema Details: {result['info']['schema_validation']}")
    else:
        print("Note: Install jsonschema library for advanced schema validation")


def cleanup_test_files():
    """Clean up test files"""
    import shutil
    if os.path.exists("test_json_files"):
        shutil.rmtree("test_json_files")
    if os.path.exists("test_validation_report.txt"):
        os.remove("test_validation_report.txt")
    print("\nTest files cleaned up.")


def main():
    """Run all tests"""
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "="*80)
    print("JSON VALIDATOR TEST SUITE")
    print("="*80)
    
    try:
        # Create test files
        print("\nCreating test files...")
        test_dir = create_test_files()
        print(f"Test files created in: {test_dir}")
        
        # Run tests
        test_single_file_validation()
        test_batch_validation()
        test_report_generation()
        test_schema_validation()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)
        
        # Ask to clean up
        try:
            response = input("\nClean up test files? (y/n): ")
            if response.lower() == 'y':
                cleanup_test_files()
            else:
                print(f"\nTest files kept in: {test_dir}")
                print("Test report: test_validation_report.txt")
        except (EOFError, KeyboardInterrupt):
            print(f"\n\nTest files kept in: {test_dir}")
            print("Test report: test_validation_report.txt")
            print("\nTo clean up manually, delete the 'test_json_files' folder and 'test_validation_report.txt'")
    
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

