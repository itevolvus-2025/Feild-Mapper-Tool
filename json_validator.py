"""
JSON Validator Module
Validates JSON files for syntax errors, schema compliance, and structural issues
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

# Try to import jsonschema for advanced validation (optional dependency)
try:
    import jsonschema
    from jsonschema import validate, ValidationError, SchemaError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JSONValidator:
    """
    Comprehensive JSON validation including:
    - Syntax validation
    - Schema validation
    - Structure validation
    - Data type validation
    """
    
    def __init__(self):
        self.validation_results = []
        self.error_count = 0
        self.warning_count = 0
    
    def validate_file(self, file_path: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate a JSON file for syntax and optional schema compliance
        
        Args:
            file_path: Path to JSON file
            schema: Optional JSON schema to validate against
        
        Returns:
            Dictionary containing validation results:
            {
                'valid': bool,
                'file': str,
                'errors': List[str],
                'warnings': List[str],
                'info': Dict
            }
        """
        result = {
            'valid': True,
            'file': file_path,
            'errors': [],
            'warnings': [],
            'info': {}
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                result['valid'] = False
                result['errors'].append(f"File not found: {file_path}")
                return result
            
            # Check file size
            file_size = os.path.getsize(file_path)
            result['info']['file_size_bytes'] = file_size
            result['info']['file_size_mb'] = round(file_size / (1024 * 1024), 2)
            
            # Warn about very large files
            if file_size > 100 * 1024 * 1024:  # 100MB
                result['warnings'].append(f"Large file size: {result['info']['file_size_mb']} MB")
            
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for empty file
            if not content.strip():
                result['valid'] = False
                result['errors'].append("File is empty")
                return result
            
            # Validate JSON syntax
            try:
                data = json.loads(content)
                result['info']['syntax'] = 'valid'
            except json.JSONDecodeError as e:
                result['valid'] = False
                result['errors'].append(f"JSON syntax error at line {e.lineno}, column {e.colno}: {e.msg}")
                result['info']['syntax'] = 'invalid'
                
                # Try to provide helpful suggestions
                suggestions = self._get_syntax_suggestions(content, e)
                if suggestions:
                    result['info']['suggestions'] = suggestions
                
                return result
            
            # Validate structure
            structure_validation = self._validate_structure(data)
            result['info'].update(structure_validation)
            
            if structure_validation.get('issues'):
                result['warnings'].extend(structure_validation['issues'])
            
            # Validate data types
            type_validation = self._validate_data_types(data)
            if type_validation.get('issues'):
                result['warnings'].extend(type_validation['issues'])
            
            # Schema validation if provided
            if schema:
                schema_validation = self._validate_schema(data, schema)
                result['info']['schema_validation'] = schema_validation
                
                if not schema_validation['valid']:
                    result['valid'] = False
                    result['errors'].extend(schema_validation['errors'])
            
            # Check for common issues
            common_issues = self._check_common_issues(data, content)
            if common_issues:
                result['warnings'].extend(common_issues)
            
        except UnicodeDecodeError as e:
            result['valid'] = False
            result['errors'].append(f"Encoding error: {str(e)}")
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Unexpected error: {str(e)}")
            logger.error(f"Validation error for {file_path}: {str(e)}", exc_info=True)
        
        return result
    
    def validate_batch(self, file_paths: List[str], schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate multiple JSON files
        
        Args:
            file_paths: List of file paths to validate
            schema: Optional JSON schema to validate against
        
        Returns:
            Dictionary containing batch validation results
        """
        results = {
            'total_files': len(file_paths),
            'valid_files': 0,
            'invalid_files': 0,
            'files_with_warnings': 0,
            'details': []
        }
        
        for file_path in file_paths:
            validation_result = self.validate_file(file_path, schema)
            results['details'].append(validation_result)
            
            if validation_result['valid']:
                results['valid_files'] += 1
            else:
                results['invalid_files'] += 1
            
            if validation_result['warnings']:
                results['files_with_warnings'] += 1
        
        return results
    
    def _validate_structure(self, data: Any) -> Dict[str, Any]:
        """Validate JSON structure and provide statistics"""
        info = {
            'root_type': type(data).__name__,
            'issues': []
        }
        
        if isinstance(data, dict):
            info['field_count'] = len(data)
            info['fields'] = list(data.keys())
            
            # Check for empty objects
            if len(data) == 0:
                info['issues'].append("Root object is empty")
            
            # Check for duplicate keys (already handled by JSON parser, but good to note)
            # Check for very deep nesting
            max_depth = self._get_max_depth(data)
            info['max_nesting_depth'] = max_depth
            if max_depth > 10:
                info['issues'].append(f"Deep nesting detected: {max_depth} levels")
        
        elif isinstance(data, list):
            info['array_length'] = len(data)
            
            if len(data) == 0:
                info['issues'].append("Root array is empty")
            else:
                # Check array element consistency
                if len(data) > 0:
                    first_type = type(data[0]).__name__
                    info['array_element_type'] = first_type
                    
                    # Check if all elements have same type
                    inconsistent = False
                    for item in data[1:]:
                        if type(item).__name__ != first_type:
                            inconsistent = True
                            break
                    
                    if inconsistent:
                        info['issues'].append("Array contains mixed element types")
                    
                    # If array of objects, check for consistent fields
                    if isinstance(data[0], dict) and len(data) > 1:
                        first_keys = set(data[0].keys())
                        inconsistent_keys = False
                        for item in data[1:]:
                            if isinstance(item, dict) and set(item.keys()) != first_keys:
                                inconsistent_keys = True
                                break
                        
                        if inconsistent_keys:
                            info['issues'].append("Array objects have inconsistent field sets")
        
        return info
    
    def _validate_data_types(self, data: Any, path: str = "root", check_nulls: bool = False) -> Dict[str, Any]:
        """
        Validate data types and check for potential issues
        
        Args:
            data: Data to validate
            path: Current path in data structure
            check_nulls: If True, report null values (default: False, as nulls are valid JSON)
        """
        issues = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}"
                
                # Only check for null values if explicitly requested (nulls are valid JSON)
                if check_nulls and value is None:
                    issues.append(f"Null value at {current_path}")
                
                # Check for empty strings (may indicate data quality issues)
                elif isinstance(value, str) and value.strip() == "":
                    issues.append(f"Empty string at {current_path}")
                
                # Recursively check nested structures
                elif isinstance(value, (dict, list)):
                    nested_validation = self._validate_data_types(value, current_path, check_nulls)
                    if nested_validation.get('issues'):
                        issues.extend(nested_validation['issues'])
        
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                current_path = f"{path}[{idx}]"
                if isinstance(item, (dict, list)):
                    nested_validation = self._validate_data_types(item, current_path, check_nulls)
                    if nested_validation.get('issues'):
                        issues.extend(nested_validation['issues'])
        
        return {'issues': issues}
    
    def _validate_schema(self, data: Any, schema: Dict) -> Dict[str, Any]:
        """
        Validate data against a JSON schema
        Uses jsonschema library if available, otherwise falls back to basic validation
        """
        result = {
            'valid': True,
            'errors': []
        }
        
        try:
            # Use jsonschema library if available (more comprehensive)
            if HAS_JSONSCHEMA:
                try:
                    jsonschema.validate(instance=data, schema=schema)
                    result['valid'] = True
                except jsonschema.ValidationError as e:
                    result['valid'] = False
                    result['errors'].append(f"Schema validation error: {e.message}")
                    if e.path:
                        path_str = '.'.join(str(p) for p in e.path)
                        result['errors'].append(f"  at path: {path_str}")
                except jsonschema.SchemaError as e:
                    result['valid'] = False
                    result['errors'].append(f"Invalid schema: {e.message}")
            else:
                # Fallback to basic validation
                # Check required fields
                if 'required' in schema and isinstance(data, dict):
                    for required_field in schema['required']:
                        if required_field not in data:
                            result['valid'] = False
                            result['errors'].append(f"Missing required field: {required_field}")
                
                # Check field types
                if 'properties' in schema and isinstance(data, dict):
                    for field, field_schema in schema['properties'].items():
                        if field in data:
                            expected_type = field_schema.get('type')
                            actual_value = data[field]
                            
                            # Type checking
                            if expected_type:
                                if not self._check_type(actual_value, expected_type):
                                    result['valid'] = False
                                    result['errors'].append(
                                        f"Field '{field}' has wrong type. Expected: {expected_type}, "
                                        f"Got: {type(actual_value).__name__}"
                                    )
        
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Schema validation error: {str(e)}")
        
        return result
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON schema type"""
        type_map = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
            'null': type(None)
        }
        
        expected_python_type = type_map.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True
    
    def _get_max_depth(self, data: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth"""
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(self._get_max_depth(v, current_depth + 1) for v in data.values())
        elif isinstance(data, list):
            if not data:
                return current_depth
            return max(self._get_max_depth(item, current_depth + 1) for item in data)
        else:
            return current_depth
    
    def _check_common_issues(self, data: Any, content: str) -> List[str]:
        """Check for common JSON issues that indicate invalid JSON"""
        issues = []
        
        # Check for comments (not valid in JSON)
        if '//' in content or '/*' in content:
            issues.append("File may contain comments (not valid in JSON)")
        
        # Check for single quotes (JSON requires double quotes)
        lines = content.split('\n')
        for i, line in enumerate(lines[:100], 1):  # Check first 100 lines
            if "'" in line and '"' not in line:
                issues.append(f"Possible single quotes on line {i} (JSON requires double quotes)")
                break
        
        # Note: Minified JSON (single-line, no indentation) is perfectly valid
        # and should NOT be reported as an issue or warning
        
        return issues
    
    def _get_syntax_suggestions(self, content: str, error: json.JSONDecodeError) -> List[str]:
        """Provide helpful suggestions based on syntax error"""
        suggestions = []
        
        # Get the problematic line
        lines = content.split('\n')
        if 0 <= error.lineno - 1 < len(lines):
            problem_line = lines[error.lineno - 1]
            
            # Check for common issues
            if 'Expecting' in error.msg:
                if 'property name' in error.msg:
                    suggestions.append("Check for missing quotes around property names")
                elif 'value' in error.msg:
                    suggestions.append("Check for trailing commas or missing values")
            
            if 'Unterminated string' in error.msg:
                suggestions.append("Check for unclosed string quotes")
            
            if problem_line.strip().endswith(','):
                suggestions.append("Check for trailing comma before closing bracket")
        
        return suggestions
    
    def generate_report(self, validation_results: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        Generate a human-readable validation report
        
        Args:
            validation_results: Results from validate_batch()
            output_path: Optional path to save report
        
        Returns:
            Report text
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("JSON VALIDATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Summary
        report_lines.append("SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Files: {validation_results['total_files']}")
        report_lines.append(f"Valid Files: {validation_results['valid_files']}")
        report_lines.append(f"Invalid Files: {validation_results['invalid_files']}")
        report_lines.append(f"Files with Warnings: {validation_results['files_with_warnings']}")
        report_lines.append("")
        
        # Details for invalid files
        if validation_results['invalid_files'] > 0:
            report_lines.append("INVALID FILES")
            report_lines.append("-" * 80)
            for detail in validation_results['details']:
                if not detail['valid']:
                    report_lines.append(f"\nFile: {os.path.basename(detail['file'])}")
                    report_lines.append(f"  Path: {detail['file']}")
                    if detail['errors']:
                        report_lines.append("  Errors:")
                        for error in detail['errors']:
                            report_lines.append(f"    - {error}")
            report_lines.append("")
        
        # Files with warnings
        if validation_results['files_with_warnings'] > 0:
            report_lines.append("FILES WITH WARNINGS")
            report_lines.append("-" * 80)
            for detail in validation_results['details']:
                if detail['warnings']:
                    report_lines.append(f"\nFile: {os.path.basename(detail['file'])}")
                    report_lines.append(f"  Path: {detail['file']}")
                    report_lines.append("  Warnings:")
                    for warning in detail['warnings']:
                        report_lines.append(f"    - {warning}")
            report_lines.append("")
        
        # Valid files summary
        report_lines.append("VALID FILES")
        report_lines.append("-" * 80)
        for detail in validation_results['details']:
            if detail['valid'] and not detail['warnings']:
                report_lines.append(f"  ✓ {os.path.basename(detail['file'])}")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        # Save to file if path provided
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                logger.info(f"Validation report saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save report: {str(e)}")
        
        return report_text

