"""
JSON Parser Module
Extracts field names from JSON files with support for nested structures
"""

import json
import os
from typing import List, Set, Dict, Any, Optional, Tuple
import logging
import shutil

# Try to import chardet for encoding detection (optional dependency)
try:
    import chardet  # type: ignore
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    chardet = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JSONParser:
    def __init__(self):
        self.field_cache = {}
        self.json_data_cache = {}  # Cache loaded JSON data to avoid reloading
        self.logged_files = set()  # Track which files we've already logged
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        Detect file encoding using multiple methods
        
        Returns:
            Detected encoding name, or 'utf-8' as default
        """
        # List of encodings to try (in order of preference)
        common_encodings = ['utf-8', 'utf-8-sig']
        
        # Try chardet if available (more accurate detection)
        if HAS_CHARDET:
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read(10000)  # Read first 10KB for detection
                    if raw_data:
                        result = chardet.detect(raw_data)
                        if result and result.get('encoding'):
                            detected_encoding = result['encoding'].lower()
                            confidence = result.get('confidence', 0)
                            # Only use if confidence is reasonable
                            if confidence > 0.7:
                                # Normalize encoding name
                                if detected_encoding.startswith('utf-8'):
                                    return 'utf-8'
                                elif detected_encoding.startswith('utf-16'):
                                    return 'utf-16'
                                # Add detected encoding to try list if not already there
                                if detected_encoding not in common_encodings:
                                    common_encodings.insert(1, detected_encoding)
            except Exception as e:
                logger.debug(f"Failed to detect encoding with chardet for {file_path}: {str(e)}")
        
        # Try common encodings in order
        for encoding in common_encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1)  # Try to read at least one character
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                continue
        
        # Default to utf-8 if all else fails
        return 'utf-8'
    
    def _read_file_with_encoding(self, file_path: str) -> Tuple[str, str]:
        """
        Read file content trying multiple encodings
        
        Returns:
            Tuple of (content, encoding_used)
        """
        # Detect encoding first
        detected_encoding = self._detect_encoding(file_path)
        
        # List of encodings to try (detected first, then fallbacks)
        encodings_to_try = [detected_encoding, 'utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be']
        # Remove duplicates while preserving order
        seen = set()
        encodings_to_try = [enc for enc in encodings_to_try if not (enc in seen or seen.add(enc))]
        
        last_error = None
        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                # If we get here, reading was successful
                if detected_encoding != encoding:
                    logger.debug(f"File {file_path} read with {encoding} (detected: {detected_encoding})")
                return content, encoding
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        
        # If all encodings fail, raise the last error
        if last_error:
            raise UnicodeDecodeError(
                last_error.encoding if hasattr(last_error, 'encoding') else 'unknown',
                last_error.object if hasattr(last_error, 'object') else b'',
                last_error.start if hasattr(last_error, 'start') else 0,
                last_error.end if hasattr(last_error, 'end') else 0,
                f"Failed to decode file with any encoding. Last error: {str(last_error)}"
            )
        else:
            raise IOError(f"Failed to read file {file_path} with any encoding")
    
    def load_json(self, file_path: str) -> Any:
        """
        Load JSON file with error handling for malformed JSON and automatic encoding detection
        
        Returns:
            Dict, List, or other JSON-serializable type depending on file content
        """
        try:
            # Read file with automatic encoding detection
            content, encoding_used = self._read_file_with_encoding(file_path)
            
            # Log encoding if different from UTF-8 (only once per file)
            if file_path not in self.logged_files and encoding_used != 'utf-8':
                logger.info(f"JSON file {file_path} detected encoding: {encoding_used}")
            
            # Check if JSON is minified (no indentation)
            is_minified = self._is_json_minified(content)
            if is_minified:
                logger.info(f"JSON file {file_path} appears to be minified (no indentation)")
            
            # Try to parse JSON (minified JSON is still valid JSON)
            try:
                data = json.loads(content)
                
                # Log the structure type for debugging (only once per file)
                if file_path not in self.logged_files:
                    if isinstance(data, list):
                        logger.info(f"JSON file {file_path} contains an array with {len(data)} record(s)")
                    elif isinstance(data, dict):
                        logger.info(f"JSON file {file_path} contains a single object")
                    else:
                        logger.info(f"JSON file {file_path} contains a {type(data).__name__} value")
                    
                    if is_minified:
                        logger.info(f"Successfully parsed minified JSON from {file_path}")
                    self.logged_files.add(file_path)
                
                return data
            except json.JSONDecodeError as e:
                # Try to fix common JSON issues
                logger.warning(f"JSON decode error in {file_path}: {str(e)}. Attempting to fix...")
                
                # Try removing BOM if present
                if content.startswith('\ufeff'):
                    content = content[1:]
                    try:
                        data = json.loads(content)
                        logger.info(f"Fixed JSON by removing BOM in {file_path}")
                        return data
                    except json.JSONDecodeError:
                        pass
                
                # Try to fix trailing commas (not valid in JSON but common mistake)
                import re
                # Remove trailing commas before } or ]
                content_fixed = re.sub(r',(\s*[}\]])', r'\1', content)
                if content_fixed != content:
                    try:
                        data = json.loads(content_fixed)
                        logger.info(f"Fixed JSON by removing trailing commas in {file_path}")
                        return data
                    except json.JSONDecodeError:
                        pass
                
                # If all fixes fail, log and return None (caller should handle)
                logger.error(f"Failed to parse JSON file {file_path}: {str(e)}")
                return None
                
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in {file_path}: {str(e)}. Tried multiple encodings.")
            return None
        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {str(e)}")
            return None
    
    def _is_json_minified(self, content: str) -> bool:
        """
        Check if JSON is minified (no indentation/formatting)
        
        Args:
            content: JSON content as string
        
        Returns:
            True if JSON appears to be minified, False otherwise
        """
        if not content or len(content.strip()) == 0:
            return False
        
        # Remove leading/trailing whitespace
        content = content.strip()
        
        # Check if it's a single line (likely minified)
        lines = content.split('\n')
        if len(lines) == 1 and len(content) > 100:
            return True
        
        # Check if there's minimal indentation (most lines have no leading spaces)
        lines_with_indent = 0
        total_lines = 0
        for line in lines[:100]:  # Check first 100 lines
            stripped = line.strip()
            if stripped and not stripped.startswith('//'):  # Skip empty lines and comments
                total_lines += 1
                if line.startswith(' ') or line.startswith('\t'):
                    lines_with_indent += 1
        
        # If less than 20% of lines have indentation, consider it minified
        if total_lines > 0 and (lines_with_indent / total_lines) < 0.2:
            return True
        
        return False
    
    def extract_fields(self, file_path: str, json_path: Optional[str] = None) -> List[str]:
        """
        Extract field names from JSON file
        
        Args:
            file_path: Path to JSON file
            json_path: Optional path to specific section (e.g., "data.fields" or "root.items")
        
        Returns:
            List of field names (empty list if file is invalid or malformed)
        """
        try:
            data = self.load_json(file_path)
            
            # If data is None or empty (malformed JSON), return empty list
            if data is None:
                logger.warning(f"Failed to load JSON from {file_path}, returning empty fields list")
                return []
            
            # Handle empty data structures
            if isinstance(data, dict) and len(data) == 0:
                logger.warning(f"Empty JSON object in {file_path}, returning empty fields list")
                return []
            if isinstance(data, list) and len(data) == 0:
                logger.warning(f"Empty JSON array in {file_path}, returning empty fields list")
                return []
            
            # If json_path is specified, navigate to that section
            if json_path:
                try:
                    data = self._navigate_path(data, json_path)
                    if data is None:
                        logger.warning(f"JSON path '{json_path}' not found in {file_path}")
                        return []
                except Exception as e:
                    logger.warning(f"Failed to navigate JSON path '{json_path}' in {file_path}: {str(e)}")
                    return []
            
            # Extract all field names
            fields = self._extract_all_fields(data)
            
            # Log summary of extraction
            if isinstance(data, list):
                logger.info(f"Extracted {len(fields)} unique fields from {len(data)} record(s) in {file_path}")
                if len(data) > 1:
                    logger.info(f"Multi-record file detected: processing all {len(data)} records to capture all possible fields")
            else:
                logger.info(f"Extracted {len(fields)} fields from {file_path}")
            
            return sorted(list(set(fields)))  # Remove duplicates and sort
            
        except Exception as e:
            logger.error(f"Failed to extract fields from {file_path}: {str(e)}")
            # Return empty list instead of raising to allow processing to continue
            return []
    
    def extract_fields_from_record(self, record: Dict, prefix: str = "") -> List[str]:
        """
        Extract field names from a single record (for per-record comparison)
        
        Args:
            record: Single JSON record (dict)
            prefix: Optional prefix for field names
        
        Returns:
            List of field names from this record
        """
        try:
            fields = self._extract_all_fields(record, prefix, exclude_categories=False)
            return sorted(list(set(fields)))
        except Exception as e:
            logger.error(f"Failed to extract fields from record: {str(e)}")
            return []
    
    def get_records(self, file_path: str, json_path: Optional[str] = None) -> List[Dict]:
        """
        Get all records from a JSON file (for per-record processing)
        
        Args:
            file_path: Path to JSON file
            json_path: Optional path to specific section
        
        Returns:
            List of records (each record is a dict). If file is a single object, returns list with one item.
        """
        try:
            data = self.load_json(file_path)
            
            if data is None:
                return []
            
            # If json_path is specified, navigate to that section
            if json_path:
                try:
                    data = self._navigate_path(data, json_path)
                    if data is None:
                        return []
                except Exception:
                    return []
            
            # If it's an array, return all items
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            # If it's a single object, return it as a list with one item
            elif isinstance(data, dict):
                return [data]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get records from {file_path}: {str(e)}")
            return []
    
    def check_null_categories(self, file_path: str, json_path: Optional[str] = None) -> Dict[str, bool]:
        """
        Check which parent categories are null or empty arrays in JSON
        
        Args:
            file_path: Path to JSON file
            json_path: Optional path to specific section
        
        Returns:
            Dictionary mapping category names to True if null or empty array, False otherwise
        """
        try:
            data = self.load_json(file_path)
            
            # If data is empty (malformed JSON), return empty dict
            if not data:
                return {}
            
            # If json_path is specified, navigate to that section
            if json_path:
                try:
                    data = self._navigate_path(data, json_path)
                    if data is None:
                        return {}
                except Exception:
                    return {}
            
            null_categories = {}
            
            if isinstance(data, dict):
                for key, value in data.items():
                    # Check if value is null or empty array
                    if value is None:
                        null_categories[key] = True
                    elif isinstance(value, list) and len(value) == 0:
                        null_categories[key] = True
                    else:
                        null_categories[key] = False
            elif isinstance(data, list):
                # Root is an array - check arrays within each record
                # Process first record to get structure (assuming all records have similar structure)
                if len(data) > 0 and isinstance(data[0], dict):
                    for key, value in data[0].items():
                        # Check if value is null or empty array
                        if value is None:
                            null_categories[key] = True
                        elif isinstance(value, list) and len(value) == 0:
                            null_categories[key] = True
                        else:
                            null_categories[key] = False
            
            return null_categories
            
        except Exception as e:
            logger.error(f"Failed to check null categories: {str(e)}")
            return {}
    
    def get_array_field_mapping(self, file_path: str, json_path: Optional[str] = None) -> Dict[str, str]:
        """
        Detect which fields are inside arrays in JSON and map them to their parent array name
        
        Args:
            file_path: Path to JSON file
            json_path: Optional path to specific section
        
        Returns:
            Dictionary mapping field_name -> array_name (empty string if not in array)
        """
        try:
            data = self.load_json(file_path)
            
            # If data is empty (malformed JSON), return empty dict
            if not data:
                return {}
            
            # If json_path is specified, navigate to that section
            if json_path:
                try:
                    data = self._navigate_path(data, json_path)
                    if data is None:
                        return {}
                except Exception:
                    return {}
            
            field_to_array = {}
            
            if isinstance(data, dict):
                for key, value in data.items():
                    # If value is an array, extract fields from array elements
                    if isinstance(value, list):
                        # Check if array is null or empty
                        if value is None or len(value) == 0:
                            continue
                        
                        # Extract fields from array elements
                        for item in value:
                            if isinstance(item, dict):
                                # All fields in this dict are from the array named 'key'
                                for field_name in item.keys():
                                    # Normalize field name
                                    normalized_field = self._normalize_field_name(field_name)
                                    field_to_array[normalized_field] = key
                    
                    # Recursively check nested structures
                    elif isinstance(value, dict):
                        nested_mapping = self._extract_array_fields_recursive(value, "")
                        field_to_array.update(nested_mapping)
            
            elif isinstance(data, list):
                # Root is an array - process each record to find arrays within them
                for item in data:
                    if isinstance(item, dict):
                        # Recursively extract array field mappings from each record
                        nested = self._extract_array_fields_recursive(item, "")
                        field_to_array.update(nested)
            
            return field_to_array
            
        except Exception as e:
            logger.error(f"Failed to get array field mapping: {str(e)}")
            return {}
    
    def _extract_array_fields_recursive(self, data: Any, parent_array: str = "") -> Dict[str, str]:
        """Recursively extract array field mappings"""
        field_to_array = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    # This is an array
                    if value is None or len(value) == 0:
                        continue
                    
                    # Extract fields from array elements
                    for item in value:
                        if isinstance(item, dict):
                            for field_name in item.keys():
                                normalized_field = self._normalize_field_name(field_name)
                                field_to_array[normalized_field] = key
                            # Also check for nested structures in array items
                            nested = self._extract_array_fields_recursive(item, key)
                            field_to_array.update(nested)
                elif isinstance(value, dict):
                    # Recursively process nested dict
                    nested = self._extract_array_fields_recursive(value, parent_array)
                    field_to_array.update(nested)
        
        return field_to_array
    
    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field name for comparison (same logic as FieldComparator)"""
        # Remove all spaces, underscores, hyphens, and dots
        normalized = field_name.replace(' ', '').replace('_', '').replace('-', '').replace('.', '')
        # Convert to lowercase
        normalized = normalized.lower()
        return normalized
    
    def _navigate_path(self, data: Any, path: str) -> Any:
        """Navigate to a specific path in JSON structure"""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)]
            else:
                raise ValueError(f"Invalid path: {path}")
            
            if current is None:
                raise ValueError(f"Path not found: {path}")
        
        return current
    
    def _extract_all_fields(self, data: Any, prefix: str = "", exclude_categories: bool = True) -> Set[str]:
        """
        Recursively extract all field names from JSON structure
        
        Args:
            data: JSON data to extract from
            prefix: Prefix for nested field names
            exclude_categories: If True, exclude top-level category names (only extract nested fields)
        """
        fields = set()
        
        if isinstance(data, dict):
            for key, value in data.items():
                # Extract the key itself as a field (category names should be compared too)
                field_name = f"{prefix}.{key}" if prefix else key
                fields.add(field_name)
                
                # Handle arrays
                if isinstance(value, list):
                    # Also extract fields from within arrays if they contain objects/dicts
                    # e.g., "bioactivity" array -> fields become "bioactivity.measure", "bioactivity.assay", etc.
                    has_objects = any(isinstance(item, dict) for item in value) if value else False
                    if has_objects:
                        array_prefix = f"{prefix}.{key}" if prefix else key
                        for item in value:
                            if isinstance(item, (dict, list)):
                                fields.update(self._extract_all_fields(item, array_prefix, exclude_categories=False))
                    continue
                
                # Recursively extract from nested structures (dicts)
                # This extracts fields inside categories, even if the category name doesn't exist in database
                # e.g., "some_new_category.field1" will be extracted and normalized to "field1" for comparison
                if isinstance(value, (dict, list)):
                    fields.update(self._extract_all_fields(value, field_name, exclude_categories=False))
        
        elif isinstance(data, list):
            # For arrays, extract fields from all elements (not just first) to catch all possible fields
            # This ensures we get all unique fields even if different records have different fields
            processed_count = 0
            fields_before = len(fields)
            
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    item_fields_before = len(fields)
                    fields.update(self._extract_all_fields(item, prefix, exclude_categories=False))
                    item_fields_added = len(fields) - item_fields_before
                    processed_count += 1
                    if not prefix and len(data) > 10:  # Only log for large arrays to avoid spam
                        # Log progress for every 100th record or at milestones
                        if (idx + 1) % 100 == 0 or idx + 1 == len(data):
                            logger.info(f"Processing record {idx + 1}/{len(data)}: {len(fields)} unique fields so far")
                    elif not prefix and len(data) <= 10:
                        # For small arrays, log each record
                        logger.info(f"Processing record {idx + 1}/{len(data)}: extracted {item_fields_added} new fields")
                elif isinstance(item, list):
                    fields.update(self._extract_all_fields(item, prefix, exclude_categories=False))
                    processed_count += 1
            
            # Log summary if we're processing multiple records
            if processed_count > 1 and not prefix:
                total_fields_added = len(fields) - fields_before
                logger.info(f"Processed {processed_count} records in array, extracted {total_fields_added} unique fields total")
        
        return fields
    
    def extract_fields_from_object(self, obj: Dict, include_nested: bool = True) -> List[str]:
        """
        Extract field names from a JSON object
        
        Args:
            obj: JSON object (dict)
            include_nested: Whether to include nested field names
        
        Returns:
            List of field names
        """
        fields = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                fields.append(key)
                
                if include_nested and isinstance(value, dict):
                    nested_fields = self.extract_fields_from_object(value, include_nested)
                    fields.extend([f"{key}.{f}" for f in nested_fields])
        
        return fields
    
    def get_field_value(self, file_path: str, field_path: str) -> Any:
        """Get value of a specific field using dot notation"""
        try:
            data = self.load_json(file_path)
            keys = field_path.split('.')
            current = data
            
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list) and key.isdigit():
                    current = current[int(key)]
                else:
                    return None
                
                if current is None:
                    return None
            
            return current
            
        except Exception as e:
            logger.error(f"Failed to get field value: {str(e)}")
            return None
    
    def compare_structure(self, file1_path: str, file2_path: str) -> Dict:
        """Compare structure of two JSON files"""
        fields1 = set(self.extract_fields(file1_path))
        fields2 = set(self.extract_fields(file2_path))
        
        return {
            'file1_only': sorted(list(fields1 - fields2)),
            'file2_only': sorted(list(fields2 - fields1)),
            'common': sorted(list(fields1 & fields2)),
            'file1_count': len(fields1),
            'file2_count': len(fields2),
            'common_count': len(fields1 & fields2)
        }
    
    def validate_json_structure(self, file_path: str, expected_fields: List[str]) -> Dict:
        """Validate that JSON file contains expected fields"""
        try:
            actual_fields = set(self.extract_fields(file_path))
            expected_fields_set = set(expected_fields)
            
            return {
                'valid': expected_fields_set.issubset(actual_fields),
                'missing': sorted(list(expected_fields_set - actual_fields)),
                'extra': sorted(list(actual_fields - expected_fields_set)),
                'matched': sorted(list(expected_fields_set & actual_fields))
            }
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'missing': expected_fields,
                'extra': [],
                'matched': []
            }
    
    def clean_special_characters(self, data: Any, database_name: str, field_path: str = "") -> Tuple[Any, int]:
        """
        Remove specific special characters from specific fields based on database configuration
        
        Args:
            data: JSON data (dict, list, or nested structure)
            database_name: Name of the database for configuration lookup
            field_path: Current field path (for nested structures)
        
        Returns:
            Tuple of (cleaned_data, characters_removed_count)
        """
        try:
            import database_config
            removal_config = getattr(database_config, 'SPECIAL_CHAR_REMOVAL', {})
            
            # If no configuration for this database, return data unchanged
            if database_name not in removal_config:
                return data, 0
            
            field_config = removal_config[database_name]
            if not field_config:
                return data, 0
            
            total_removed = 0
            
            # Normalize field names for comparison (lowercase, remove spaces/underscores/hyphens)
            def normalize_name(name: str) -> str:
                return name.lower().replace(' ', '').replace('_', '').replace('-', '').replace('.', '').replace(':', '')
            
            # Create normalized lookup dictionary
            normalized_config = {}
            for field_name, chars_to_remove in field_config.items():
                normalized_name = normalize_name(field_name)
                normalized_config[normalized_name] = chars_to_remove
            
            if isinstance(data, dict):
                cleaned_data = {}
                for key, value in data.items():
                    # Check if this field should have characters removed
                    normalized_key = normalize_name(key)
                    current_path = f"{field_path}.{key}" if field_path else key
                    
                    if normalized_key in normalized_config:
                        chars_to_remove = normalized_config[normalized_key]
                        if isinstance(value, str):
                            # Remove specified characters from string value
                            original_value = value
                            for char in chars_to_remove:
                                value = value.replace(char, '')
                            removed_count = len(original_value) - len(value)
                            total_removed += removed_count
                            if removed_count > 0:
                                logger.debug(f"Removed {removed_count} special character(s) from field '{current_path}' in {database_name}")
                            cleaned_data[key] = value
                        elif isinstance(value, (dict, list)):
                            # Recursively clean nested structures
                            cleaned_value, removed = self.clean_special_characters(value, database_name, current_path)
                            cleaned_data[key] = cleaned_value
                            total_removed += removed
                        else:
                            cleaned_data[key] = value
                    elif isinstance(value, (dict, list)):
                        # Recursively process nested structures even if field name doesn't match
                        cleaned_value, removed = self.clean_special_characters(value, database_name, current_path)
                        cleaned_data[key] = cleaned_value
                        total_removed += removed
                    else:
                        cleaned_data[key] = value
                
                return cleaned_data, total_removed
            
            elif isinstance(data, list):
                cleaned_list = []
                for idx, item in enumerate(data):
                    current_path = f"{field_path}[{idx}]" if field_path else f"[{idx}]"
                    if isinstance(item, (dict, list)):
                        cleaned_item, removed = self.clean_special_characters(item, database_name, current_path)
                        cleaned_list.append(cleaned_item)
                        total_removed += removed
                    else:
                        cleaned_list.append(item)
                
                return cleaned_list, total_removed
            
            else:
                return data, 0
                
        except Exception as e:
            logger.error(f"Error cleaning special characters: {str(e)}", exc_info=True)
            return data, 0
    
    def save_cleaned_json(self, original_file_path: str, cleaned_data: Any, output_dir: str = None) -> Optional[str]:
        """
        Save cleaned JSON data to a file
        
        Args:
            original_file_path: Path to original JSON file
            cleaned_data: Cleaned JSON data
            output_dir: Directory to save cleaned file (default: 'cleaned_json' folder next to original)
        
        Returns:
            Path to saved cleaned file, or None if failed
        """
        try:
            if output_dir is None:
                # Create 'cleaned_json' folder in the same directory as the original file
                original_dir = os.path.dirname(os.path.abspath(original_file_path))
                output_dir = os.path.join(original_dir, 'cleaned_json')
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output filename (keep original name)
            original_filename = os.path.basename(original_file_path)
            output_path = os.path.join(output_dir, original_filename)
            
            # Write cleaned JSON with proper indentation
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved cleaned JSON to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to save cleaned JSON: {str(e)}", exc_info=True)
            return None

