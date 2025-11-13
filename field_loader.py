"""
Field Loader Module
Allows direct loading of database/table field information from code
"""

from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FieldLoader:
    """
    Class to load database and table field information directly from code
    """
    
    def __init__(self):
        self.databases: Dict[str, Dict[str, List[str]]] = {}
    
    def add_database(self, database_name: str):
        """Add a new database"""
        if database_name not in self.databases:
            self.databases[database_name] = {}
            logger.info(f"Added database: {database_name}")
        return self
    
    def add_table(self, database_name: str, table_name: str, fields: List[str]):
        """
        Add a table with fields to a database
        
        Args:
            database_name: Name of the database
            table_name: Name of the table
            fields: List of field names
        
        Returns:
            self for method chaining
        """
        if database_name not in self.databases:
            self.add_database(database_name)
        
        self.databases[database_name][table_name] = fields
        logger.info(f"Added table '{table_name}' to database '{database_name}' with {len(fields)} fields")
        return self
    
    def add_fields(self, database_name: str, table_name: str, fields: List[str]):
        """Add fields to an existing table (or create if doesn't exist)"""
        if database_name not in self.databases:
            self.add_database(database_name)
        
        if table_name not in self.databases[database_name]:
            self.databases[database_name][table_name] = []
        
        self.databases[database_name][table_name].extend(fields)
        # Remove duplicates while preserving order
        self.databases[database_name][table_name] = list(dict.fromkeys(self.databases[database_name][table_name]))
        logger.info(f"Added {len(fields)} fields to table '{table_name}' in database '{database_name}'")
        return self
    
    def get_databases(self) -> List[str]:
        """Get list of all database names"""
        return list(self.databases.keys())
    
    def get_tables(self, database_name: str) -> List[str]:
        """Get list of tables for a specific database"""
        if database_name in self.databases:
            db_data = self.databases[database_name]
            # If database directly contains a list, it's a simple structure (no tables)
            if isinstance(db_data, list):
                return []  # No tables, just fields
            # Otherwise, return table names
            elif isinstance(db_data, dict):
                return list(db_data.keys())
        return []
    
    def get_field_category_mapping(self, database_name: str) -> Dict[str, str]:
        """
        Get mapping of field names to their parent categories
        
        Args:
            database_name: Name of the database
        
        Returns:
            Dictionary mapping field_name -> category_name
        """
        mapping = {}
        
        if database_name in self.databases:
            db_data = self.databases[database_name]
            
            # Table structure: database contains tables/categories
            if isinstance(db_data, dict):
                for category, fields in db_data.items():
                    if isinstance(fields, list):
                        for field in fields:
                            mapping[field] = category
                    elif isinstance(fields, dict):
                        # Handle nested structures
                        nested_fields = self._flatten_nested_fields(fields)
                        for field in nested_fields:
                            mapping[field] = category
        
        return mapping
    
    def get_fields(self, database_name: str, table_name: str = None) -> List[str]:
        """
        Get field names for a specific database
        
        Args:
            database_name: Name of the database
            table_name: Optional table name (if None, returns all fields from database)
        """
        if database_name in self.databases:
            db_data = self.databases[database_name]
            
            # Simple structure: database directly contains a list of fields
            if isinstance(db_data, list):
                return db_data
            
            # Table structure: database contains tables
            elif isinstance(db_data, dict):
                if table_name:
                    # Get fields from specific table
                    if table_name in db_data:
                        table_data = db_data[table_name]
                        # If table_data is a list, return it
                        if isinstance(table_data, list):
                            return table_data
                        # If table_data is a dict (nested), flatten it
                        elif isinstance(table_data, dict):
                            return self._flatten_nested_fields(table_data)
                else:
                    # No table specified, get all fields from all tables
                    all_fields = []
                    for table_data in db_data.values():
                        if isinstance(table_data, list):
                            all_fields.extend(table_data)
                        elif isinstance(table_data, dict):
                            all_fields.extend(self._flatten_nested_fields(table_data))
                    # Keep all fields including duplicates (from different arrays/categories)
                    return all_fields
        return []
    
    def _flatten_nested_fields(self, nested_data: Dict) -> List[str]:
        """Recursively flatten nested dictionary structures to extract all fields"""
        fields = []
        for key, value in nested_data.items():
            if isinstance(value, list):
                # Direct list of fields
                fields.extend(value)
            elif isinstance(value, dict):
                # Nested dictionary, recurse
                fields.extend(self._flatten_nested_fields(value))
        return fields
    
    def get_all_data(self) -> Dict[str, Dict[str, List[str]]]:
        """Get all database/table/field data"""
        return self.databases.copy()
    
    def clear(self):
        """Clear all data"""
        self.databases = {}
        logger.info("Cleared all database data")
    
    def load_from_dict(self, data: Dict):
        """
        Load data from a dictionary structure (supports nested structures)
        
        Args:
            data: Dictionary with structure {
                'database_name': {
                    'table_name': ['field1', 'field2', ...]  # Simple
                    OR
                    'table_name': {                          # Nested
                        'category': {
                            'sub_table': ['field1', ...]
                        }
                    }
                }
            }
        """
        self.databases = data.copy()
        logger.info(f"Loaded {len(self.databases)} databases from dictionary")
        return self
    
    def load_from_config_file(self, config_file: str):
        """
        Load from a Python configuration file
        
        The config file should define a function or variable that returns
        the database structure.
        """
        import importlib.util
        import os
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        spec = importlib.util.spec_from_file_location("config", config_file)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        # Look for common function/variable names
        if hasattr(config_module, 'get_databases'):
            data = config_module.get_databases()
        elif hasattr(config_module, 'DATABASES'):
            data = config_module.DATABASES
        elif hasattr(config_module, 'databases'):
            data = config_module.databases
        else:
            raise ValueError("Config file must define 'get_databases()' function or 'DATABASES' variable")
        
        self.load_from_dict(data)
        return self


# Example usage and helper functions
def create_example_config():
    """
    Example function showing how to define database structures
    """
    loader = FieldLoader()
    
    # Method 1: Using method chaining
    loader.add_database("ADME Database") \
          .add_table("Pharmacokinetic Database", ["MolStructure", "CompoundID", "Species", "Route"]) \
          .add_table("Microsomal Stability Database", ["MolStructure", "CompoundID", "Enzyme"])
    
    # Method 2: Step by step
    loader.add_database("Antibody Drug Conjugate Database")
    loader.add_table("Antibody Drug Conjugate Database", "ADC Table", 
                    ["LinkerID", "PayloadID", "AntibodyID"])
    
    # Method 3: Add fields incrementally
    loader.add_database("OncoGen Database")
    loader.add_table("OncoGen Database", "Biomarker Module", ["Gene", "Mutation"])
    loader.add_fields("OncoGen Database", "Biomarker Module", ["Variant", "Frequency"])
    
    return loader.get_all_data()


# Example configuration structure
EXAMPLE_DATABASES = {
    "ADME Database": {
        "Pharmacokinetic Database": [
            "MolStructure",
            "CompoundID",
            "Species",
            "Route",
            "Dose",
            "Clearance",
            "Volume"
        ],
        "Microsomal Stability Database": [
            "MolStructure",
            "CompoundID",
            "Enzyme",
            "Stability",
            "HalfLife"
        ]
    },
    "Antibody Drug Conjugate Database": {
        "ADC Table": [
            "LinkerID",
            "PayloadID",
            "AntibodyID",
            "ConjugationSite"
        ]
    },
    "OncoGen Database": {
        "Biomarker Genomic/Molecular Alteration Module": [
            "Gene",
            "Mutation",
            "Variant",
            "Frequency"
        ],
        "Clinical trials Module": [
            "TrialID",
            "Phase",
            "Status"
        ]
    }
}

