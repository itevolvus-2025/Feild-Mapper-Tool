"""
Field Comparator Module
Compares database fields with JSON fields and provides matching results
"""

from typing import List, Dict, Set, Tuple, Any, Optional
import logging
import re
import json
import os
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FieldComparator:
    def __init__(self, case_sensitive: bool = False, fuzzy_match: bool = True, 
                 similarity_threshold: float = 0.8):
        """
        Initialize comparator
        
        Args:
            case_sensitive: Whether field name comparison should be case sensitive
            fuzzy_match: Whether to use fuzzy matching for similar field names
            similarity_threshold: Minimum similarity score for fuzzy matching (0-1)
        """
        self.case_sensitive = case_sensitive
        self.fuzzy_match = fuzzy_match
        self.similarity_threshold = similarity_threshold
        
        # Default fields to exclude from special character validation
        # These fields are expected to contain special characters (like SMILES notation, HELM notation, etc.)
        self.default_excluded_from_validation = {
            'helm', 'helms', 'helmnotation', 'helm_notation',
            'molstructure', 'molstructure_smiles', 'molstructuresmiles',
            'smiles', 'smile', 'smiles_notation', 'smilesnotation',
            'fragment_similarity', 'fragmentsimilarity',
            'fragment_similarity_smiles', 'fragmentsimilaritysmiles',
            'pbm_smiles', 'ubm_smiles', 'pd_smiles', 'photolabile_smiles',
            'modification_in_smiles', 'modificationinsmiles','parameters', 'parameter'
        }
        
        # Database-specific excluded keywords (can be set per database)
        self.database_excluded_keywords = {}  # Format: {database_name: [list of keywords]}
        
        # Store validation results
        self.validation_results = {'db': [], 'json': []}
    
    def set_database_excluded_keywords(self, database_name: str, excluded_keywords: List[str]):
        """
        Set excluded keywords for a specific database
        
        Args:
            database_name: Name of the database
            excluded_keywords: List of keywords to exclude from special character validation
        """
        self.database_excluded_keywords[database_name] = excluded_keywords
    
    def compare(self, db_fields: List[str], json_fields: List[str], 
                table_name: str = "", json_file: str = "",
                field_category_mapping: Dict[str, str] = None,
                null_categories: Dict[str, bool] = None,
                array_field_mapping: Dict[str, str] = None,
                json_data: Any = None,
                database_name: str = "") -> List[Dict]:
        """
        Compare database fields with JSON fields
        
        Args:
            db_fields: List of database field names
            json_fields: List of JSON field names
            table_name: Name of database table (for reporting)
            json_file: Path to JSON file (for reporting)
            field_category_mapping: Dictionary mapping field_name -> category_name
            null_categories: Dictionary mapping category_name -> True if null in JSON
            array_field_mapping: Dictionary mapping field_name -> array_name (from JSON)
        
        Returns:
            List of comparison results
        """
        # Normalize field names and create mapping from normalized to original
        db_fields_normalized = self._normalize_fields(db_fields)
        json_fields_normalized = self._normalize_fields(json_fields)
        
        # Create mapping from normalized to original field names
        db_normalized_to_original = {norm: orig for norm, orig in zip(db_fields_normalized, db_fields)}
        json_normalized_to_original = {norm: orig for norm, orig in zip(json_fields_normalized, json_fields)}
        
        # Normalize category mappings
        normalized_category_mapping = {}
        if field_category_mapping:
            for field, category in field_category_mapping.items():
                normalized_field = self._normalize_fields([field])[0]
                normalized_category_mapping[normalized_field] = category
        
        # Normalize null categories (remove spaces, underscores, hyphens, convert to lowercase)
        normalized_null_categories = {}
        if null_categories:
            for category, is_null in null_categories.items():
                # Remove spaces, underscores, and hyphens, convert to lowercase if not case sensitive
                normalized_category = category.replace(' ', '').replace('_', '').replace('-', '')
                if not self.case_sensitive:
                    normalized_category = normalized_category.lower()
                normalized_null_categories[normalized_category] = is_null
        
        # Normalize array field mapping
        normalized_array_mapping = {}
        if array_field_mapping:
            for field, array_name in array_field_mapping.items():
                normalized_field = self._normalize_fields([field])[0]
                # Normalize array name
                normalized_array = array_name.replace(' ', '').replace('_', '').replace('-', '')
                if not self.case_sensitive:
                    normalized_array = normalized_array.lower()
                normalized_array_mapping[normalized_field] = normalized_array
        
        results = []
        
        # Find matches
        matched_pairs = self._find_matches(db_fields_normalized, json_fields_normalized)
        
        # Process matched fields
        for db_field, json_field, match_type in matched_pairs:
            # Check if field is from an array that is null/empty
            array_name = normalized_array_mapping.get(db_field)
            array_is_null = False
            if array_name:
                # Check if the array is null/empty
                array_is_null = normalized_null_categories.get(array_name, False)
            
            # Check if field's category is null in JSON (for non-array fields)
            category = normalized_category_mapping.get(db_field)
            category_is_null = False
            if category and not array_name:  # Only check category if not already in array
                # Normalize category name (remove spaces, underscores, hyphens, convert to lowercase)
                normalized_cat = category.replace(' ', '').replace('_', '').replace('-', '')
                if not self.case_sensitive:
                    normalized_cat = normalized_cat.lower()
                category_is_null = normalized_null_categories.get(normalized_cat, False)
            
            # If array or category is null, skip this match (don't count as matched or unmatched)
            if array_is_null or category_is_null:
                continue  # Skip fields from null/empty arrays or categories
            
            # Get original field names for display
            original_db_field = db_normalized_to_original.get(db_field, db_field)
            original_json_field = json_normalized_to_original.get(json_field, json_field)
            
            results.append({
                'field_name': original_db_field,  # Use original for display
                'db_field': original_db_field,
                'json_field': original_json_field,
                'status': 'matched',
                'match_type': match_type,
                'table_name': table_name,
                'json_file': json_file
            })
        
        # Find unmatched database fields
        matched_db_fields = {pair[0] for pair in matched_pairs}
        for db_field in db_fields_normalized:
            if db_field not in matched_db_fields:
                # Check if field is from an array that is null/empty
                array_name = normalized_array_mapping.get(db_field)
                array_is_null = False
                if array_name:
                    # Check if the array is null/empty
                    array_is_null = normalized_null_categories.get(array_name, False)
                
                # Check if field's category is null in JSON (for non-array fields)
                category = normalized_category_mapping.get(db_field)
                category_is_null = False
                if category and not array_name:  # Only check category if not already in array
                    # Normalize category name (remove spaces, underscores, hyphens, convert to lowercase)
                    normalized_cat = category.replace(' ', '').replace('_', '').replace('-', '')
                    if not self.case_sensitive:
                        normalized_cat = normalized_cat.lower()
                    category_is_null = normalized_null_categories.get(normalized_cat, False)
                
                # If array/category is null but field exists in database config, still report it as unmatched_db
                # This allows fields from null arrays to be properly tracked (missing in JSON)
                # Only skip if the field is not in the database config mapping (not a valid database field)
                # If field IS in database config (in normalized_category_mapping), include it even if array is null
                if (array_is_null or category_is_null) and db_field not in normalized_category_mapping:
                    continue  # Skip only if not a valid database field (not in config)
                
                # Get original field name for display
                original_db_field = db_normalized_to_original.get(db_field, db_field)
                
                results.append({
                    'field_name': original_db_field,  # Use original for display
                    'db_field': original_db_field,
                    'json_field': '',
                    'status': 'unmatched_db',
                    'match_type': 'not_found',
                    'table_name': table_name,
                    'json_file': json_file,
                    'category': category if category else ''
                })
        
        # Find unmatched JSON fields
        matched_json_fields = {pair[1] for pair in matched_pairs}
        for json_field in json_fields_normalized:
            if json_field not in matched_json_fields:
                # Get original field name for display
                original_json_field = json_normalized_to_original.get(json_field, json_field)
                
                results.append({
                    'field_name': original_json_field,  # Use original for display
                    'db_field': '',
                    'json_field': original_json_field,
                    'status': 'unmatched_json',
                    'match_type': 'not_found',
                    'table_name': table_name,
                    'json_file': json_file
                })
        
        logger.info(f"Comparison complete: {len(matched_pairs)} matches found")
        
        # Validate field VALUES for special characters (if JSON data is provided)
        if json_data is not None:
            self._validate_field_values(json_data, json_fields, table_name, json_file, database_name)
        
        return results
    
    def _validate_field_values(self, json_data: Any, json_fields: List[str], 
                               table_name: str = "", json_file: str = "", database_name: str = ""):
        """
        Validate field VALUES for special characters (excluding certain fields)
        
        Args:
            json_data: The actual JSON data (dict, list, or nested structure)
            json_fields: List of JSON field names (paths)
            table_name: Name of database table (for reporting)
            json_file: Path to JSON file (for reporting)
        """
        json_fields_with_special_chars = []
        
        # Read file content to find line numbers
        file_content_lines = None
        if json_file and os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_content_lines = f.readlines()
            except Exception as e:
                logger.warning(f"Could not read file for line number tracking: {str(e)}")
        
        # Extract all field values from JSON data
        field_values = self._extract_field_values(json_data, json_fields)
        logger.debug(f"Validating {len(field_values)} field values for special characters in {json_file}")
        
        for field_path, value in field_values.items():
            # Skip if field should be excluded from validation (using database-specific exclusions)
            if self._is_excluded_field_with_database(field_path, database_name):
                continue
            
            # Only check string values - skip arrays/objects as they're structured data
            # Arrays and objects are valid JSON structures, their brackets/braces are not "special characters"
            if isinstance(value, str) and value:
                # Check if string is a JSON array/object representation
                # If it is, skip validation as brackets/braces are part of the structure, not special characters
                value_stripped = value.strip()
                if (value_stripped.startswith('[') and value_stripped.endswith(']')) or \
                   (value_stripped.startswith('{') and value_stripped.endswith('}')):
                    # Try to parse as JSON - if valid, it's structured data, skip validation
                    try:
                        json.loads(value)
                        # Valid JSON array/object - skip validation (brackets/braces are structure, not special chars)
                        continue
                    except (json.JSONDecodeError, ValueError):
                        # Not valid JSON, might be a string that happens to start/end with brackets
                        # Continue with normal validation
                        pass
                
                # Check if value contains special characters
                special_chars = self._get_special_characters_in_value(value)
                # Only add if special_chars is not empty (has actual special characters)
                if special_chars and len(special_chars) > 0:
                    # Find line number for this value
                    line_number = self._find_line_number(file_content_lines, field_path, value) if file_content_lines else None
                    
                    json_fields_with_special_chars.append({
                        'field': field_path,
                        'special_chars': special_chars,
                        'sample_value': value[:100] if len(value) > 100 else value,  # Store sample value (first 100 chars)
                        'file': json_file,
                        'line_number': line_number
                    })
            elif isinstance(value, (list, dict)):
                # Skip validation for arrays/objects - they're structured data, not text values
                # If you need to validate content inside arrays, validate the individual string elements recursively
                # but don't flag the structure delimiters (brackets/braces) as special characters
                pass
        
        # Store validation results with special character details including file and line number
        self.validation_results['json'].extend([{
            'field': f['field'], 
            'special_chars': f['special_chars'], 
            'sample_value': f.get('sample_value', ''), 
            'file': json_file,
            'line_number': f.get('line_number')
        } for f in json_fields_with_special_chars])
        
        # Log warnings if special characters found (with details)
        if json_fields_with_special_chars:
            for field_info in json_fields_with_special_chars:
                chars_str = ', '.join([f"'{c}'" for c in field_info['special_chars']])
                sample = field_info.get('sample_value', '')
                logger.warning(f"JSON field '{field_info['field']}' in {json_file} has value with special characters [{chars_str}]: {sample[:50]}...")
        else:
            logger.debug(f"No special characters found in field values for {json_file}")
    
    def _extract_field_values(self, data: Any, field_paths: List[str]) -> Dict[str, Any]:
        """
        Extract values for given field paths from JSON data
        
        Args:
            data: JSON data (dict, list, or nested structure)
            field_paths: List of field paths (e.g., ['field1', 'nested.field2', 'array.0.field3'])
        
        Returns:
            Dictionary mapping field paths to their values
        """
        field_values = {}
        
        # Handle root-level arrays
        if isinstance(data, list):
            # Process all records in the array
            for record_idx, record in enumerate(data):
                if isinstance(record, dict):
                    for field_path in field_paths:
                        value = self._get_value_by_path(record, field_path)
                        if value is not None:
                            # Use field path as key, store first non-null value found
                            if field_path not in field_values:
                                field_values[field_path] = value
        elif isinstance(data, dict):
            # Single object
            for field_path in field_paths:
                value = self._get_value_by_path(data, field_path)
                if value is not None:
                    field_values[field_path] = value
        
        return field_values
    
    def _get_value_by_path(self, obj: Any, field_path: str) -> Any:
        """
        Get value from object using dot-notation path
        
        Args:
            obj: Object to traverse (dict, list, etc.)
            field_path: Dot-separated path (e.g., 'bioactivity.measure')
        
        Returns:
            Value at path, or None if not found
        """
        try:
            keys = field_path.split('.')
            current = obj
            
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list):
                    # For arrays, check first element
                    if len(current) > 0 and isinstance(current[0], dict):
                        current = current[0].get(key)
                    else:
                        return None
                else:
                    return None
                
                if current is None:
                    return None
            
            return current
        except Exception:
            return None
    
    def _get_special_characters_in_value(self, value: str) -> List[str]:
        """
        Get the list of special characters found in a field value
        
        Args:
            value: Field value to check
        
        Returns:
            List of special characters found in the value
        """
        # Allowed characters: letters, numbers, spaces, common punctuation, and basic symbols
        # We're more lenient with values than field names
        # Allow: letters, numbers, spaces, underscores, hyphens, dots, parentheses, commas, colons, semicolons, quotes
        allowed_pattern = re.compile(r'[a-zA-Z0-9\s_\-\.\(\)\,\:\;\"\']')
        
        # Find all characters that are NOT in the allowed set
        special_chars = []
        for char in value:
            if not allowed_pattern.match(char):
                if char not in special_chars:
                    special_chars.append(char)
        
        return special_chars
    
    def _find_line_number(self, file_content_lines: Optional[List[str]], field_path: str, value: str) -> Optional[int]:
        """
        Find the line number in the file where a field value appears
        
        Args:
            file_content_lines: List of file lines (from readlines())
            field_path: Field path (e.g., "in_vitro_bioactivity.pk_vitro_compound_status")
            value: The value to search for
            
        Returns:
            Line number (1-indexed) or None if not found
        """
        if not file_content_lines or not value:
            return None
        
        # Try to find the value in the file
        # First, try to find by field name and value together for better accuracy
        field_name = field_path.split('.')[-1]  # Get the last part of the path
        
        # Escape special regex characters in value
        value_escaped = re.escape(value[:50])  # Use first 50 chars to avoid very long patterns
        
        # Search for the field name followed by the value
        for line_num, line in enumerate(file_content_lines, 1):
            # Check if line contains both field name (case-insensitive) and value
            if field_name.lower() in line.lower() and value_escaped in line:
                return line_num
        
        # If not found, try just the value
        for line_num, line in enumerate(file_content_lines, 1):
            if value_escaped in line:
                return line_num
        
        return None
    
    def get_validation_results(self) -> Dict[str, List]:
        """
        Get validation results for fields with special characters
        
        Returns:
            Dictionary with 'db' and 'json' keys containing lists of fields with special characters
        """
        return self.validation_results.copy()
    
    def clear_validation_results(self):
        """Clear stored validation results"""
        self.validation_results = {'db': [], 'json': []}
    
    def _has_special_characters(self, field_name: str) -> bool:
        """
        Check if field name contains special characters (excluding allowed separators)
        
        Args:
            field_name: Field name to check
        
        Returns:
            True if field contains special characters, False otherwise
        """
        # Allowed characters: letters, numbers, spaces, underscores, hyphens, dots, parentheses
        # Special characters are anything else
        allowed_pattern = re.compile(r'^[a-zA-Z0-9\s_\-\.\(\)]+$')
        
        # Check if field contains any characters outside the allowed set
        if not allowed_pattern.match(field_name):
            return True
        
        return False
    
    def _get_special_characters(self, field_name: str) -> List[str]:
        """
        Get the list of special characters found in a field name
        
        Args:
            field_name: Field name to check
        
        Returns:
            List of special characters found in the field name
        """
        # Allowed characters: letters, numbers, spaces, underscores, hyphens, dots, parentheses
        allowed_pattern = re.compile(r'[a-zA-Z0-9\s_\-\.\(\)]')
        
        # Find all characters that are NOT in the allowed set
        special_chars = []
        for char in field_name:
            if not allowed_pattern.match(char):
                if char not in special_chars:
                    special_chars.append(char)
        
        return special_chars
    
    def _is_excluded_field(self, field_name: str) -> bool:
        """
        Check if field should be excluded from special character validation
        (Uses default exclusions only - for backward compatibility)
        
        Args:
            field_name: Field name to check
        
        Returns:
            True if field should be excluded, False otherwise
        """
        return self._is_excluded_field_with_database(field_name, "")
    
    def _is_excluded_field_with_database(self, field_name: str, database_name: str = "") -> bool:
        """
        Check if field should be excluded from special character validation
        Uses database-specific excluded keywords if available
        
        Fields containing: helm, molstructure, smiles/smile are excluded
        as they are expected to contain special characters (like SMILES notation, HELM notation, etc.)
        
        Args:
            field_name: Field name to check
            database_name: Name of the database (for database-specific exclusions)
        
        Returns:
            True if field should be excluded, False otherwise
        """
        # Normalize field name for comparison (lowercase, remove spaces, underscores, hyphens, dots, colons)
        normalized = field_name.lower().replace(' ', '').replace('_', '').replace('-', '').replace('.', '').replace(':', '')
        
        # Check if normalized field name matches any default excluded pattern
        for excluded in self.default_excluded_from_validation:
            if excluded in normalized or normalized in excluded:
                return True
        
        # Get database-specific excluded keywords
        excluded_keywords = []
        if database_name and database_name in self.database_excluded_keywords:
            excluded_keywords = self.database_excluded_keywords[database_name]
        
        # Normalize field name for keyword matching (lowercase, remove spaces, underscores, hyphens, dots, colons)
        field_normalized = field_name.lower().replace(' ', '').replace('_', '').replace('-', '').replace('.', '').replace(':', '')
        
        # Check if field name contains excluded keywords (normalize both field and keyword)
        for keyword in excluded_keywords:
            # Normalize keyword the same way (lowercase, remove spaces, underscores, hyphens, dots, colons)
            keyword_normalized = keyword.lower().replace(' ', '').replace('_', '').replace('-', '').replace('.', '').replace(':', '')
            if keyword_normalized in field_normalized:
                return True
        
        # Also check default excluded patterns (common variations)
        # Use normalized field name for these checks too
        # Check for "MolStructure" (case variations)
        if 'molstructure' in field_normalized or 'molstructure' in normalized:
            return True
        
        # Check for "HELM" variations
        if 'helm' in field_normalized or 'helm' in normalized:
            return True
        
        # Check for "SMILES" variations
        if 'smiles' in field_normalized or 'smile' in field_normalized:
            return True
        
        return False
    
    def _normalize_fields(self, fields: List[str]) -> List[str]:
        """
        Normalize field names for comparison
        - Removes all spaces (internal and external)
        - Normalizes underscores, hyphens, and dots (treats them as equivalent to spaces)
        - Handles dot notation by removing parent prefixes (e.g., "PD.PD_Formula" -> "PD_Formula")
        - Converts to lowercase if case_sensitive is False
        """
        normalized = []
        for f in fields:
            # Handle dot notation: if field has dots, try to extract the actual field name
            # e.g., "PD.PD_Formula" -> "PD_Formula", "PD_Data.PD_Parameter" -> "PD_Parameter"
            if '.' in f:
                parts = f.split('.')
                # Use the last part as the field name (most specific)
                field_name = parts[-1]
                # But also check if the parent and field have the same prefix
                # e.g., "PD.PD_Formula" -> parent is "PD", field is "PD_Formula"
                # In this case, we want just "PD_Formula" or "Formula" depending on context
                if len(parts) > 1:
                    parent = parts[-2]
                    # If field starts with parent prefix, remove it
                    # e.g., "PD_Formula" starts with "PD_", so we could use just "Formula"
                    # But actually, let's keep the full field name for now
                    # The key is to normalize both the dot notation and non-dot notation versions
                    normalized_field = field_name
                else:
                    normalized_field = f
            else:
                normalized_field = f
            
            # Remove all spaces, underscores, hyphens, and dots (treat them all as separators)
            normalized_field = normalized_field.replace(' ', '').replace('_', '').replace('-', '').replace('.', '')
            # Convert to lowercase if not case sensitive
            if not self.case_sensitive:
                normalized_field = normalized_field.lower()
            normalized.append(normalized_field)
        return normalized
    
    def _find_matches(self, db_fields: List[str], json_fields: List[str]) -> List[Tuple[str, str, str]]:
        """
        Find matching pairs between database and JSON fields
        
        Returns:
            List of tuples: (db_field, json_field, match_type)
        """
        matches = []
        used_json_fields = set()
        
        # First pass: exact matches
        for db_field in db_fields:
            if db_field in json_fields and db_field not in used_json_fields:
                matches.append((db_field, db_field, 'exact'))
                used_json_fields.add(db_field)
        
        # Second pass: fuzzy matches (if enabled)
        if self.fuzzy_match:
            for db_field in db_fields:
                if db_field not in [m[0] for m in matches]:
                    best_match = self._find_best_fuzzy_match(
                        db_field, 
                        [f for f in json_fields if f not in used_json_fields]
                    )
                    if best_match:
                        json_field, similarity = best_match
                        if similarity >= self.similarity_threshold:
                            matches.append((db_field, json_field, f'fuzzy ({similarity:.2f})'))
                            used_json_fields.add(json_field)
        
        return matches
    
    def _find_best_fuzzy_match(self, field: str, candidates: List[str]) -> Tuple[str, float]:
        """Find best fuzzy match for a field"""
        best_match = None
        best_similarity = 0.0
        
        for candidate in candidates:
            similarity = self._calculate_similarity(field, candidate)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        
        if best_match:
            return (best_match, best_similarity)
        return None
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, str1, str2).ratio()
    
    def get_statistics(self, results: List[Dict]) -> Dict:
        """Get statistics from comparison results"""
        stats = {
            'total': len(results),
            'matched': 0,
            'unmatched_db': 0,
            'unmatched_json': 0,
            'exact_matches': 0,
            'fuzzy_matches': 0
        }
        
        for result in results:
            status = result.get('status', '')
            match_type = result.get('match_type', '')
            
            if status == 'matched':
                stats['matched'] += 1
                if 'exact' in match_type.lower():
                    stats['exact_matches'] += 1
                elif 'fuzzy' in match_type.lower():
                    stats['fuzzy_matches'] += 1
            elif status == 'unmatched_db':
                stats['unmatched_db'] += 1
            elif status == 'unmatched_json':
                stats['unmatched_json'] += 1
        
        return stats
    
    def generate_mapping_suggestions(self, db_fields: List[str], 
                                     json_fields: List[str]) -> Dict[str, str]:
        """
        Generate field mapping suggestions
        
        Returns:
            Dictionary mapping database fields to suggested JSON fields
        """
        suggestions = {}
        db_fields_normalized = self._normalize_fields(db_fields)
        json_fields_normalized = self._normalize_fields(json_fields)
        
        for db_field in db_fields_normalized:
            # Try exact match first
            if db_field in json_fields_normalized:
                suggestions[db_field] = db_field
            elif self.fuzzy_match:
                # Try fuzzy match
                best_match = self._find_best_fuzzy_match(
                    db_field, 
                    json_fields_normalized
                )
                if best_match:
                    json_field, similarity = best_match
                    if similarity >= self.similarity_threshold:
                        suggestions[db_field] = json_field
        
        return suggestions

