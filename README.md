# Field Mapper - Annexure to JSON Comparison Tool

A desktop application built with Python that compares field names from database annexures with fields in JSON files. This tool helps identify matching and mismatched fields between your database schema documentation and JSON data structures.

## Features

- **Annexure Support**: Pre-configured support for 11 database annexures including Theme Database, Biomarker Module, Clinical Trials, and more
- **JSON Field Extraction**: 
  - Automatically extract field names from JSON files, including deeply nested structures
  - Support for nested arrays with intelligent field path resolution
  - Recursive folder scanning (finds JSON files in all subfolders)
  - Handles both direct JSON files and multi-level folder structures
- **Intelligent Matching**: 
  - Exact field name matching with normalization
  - Fuzzy matching for similar field names (configurable similarity threshold)
  - Case-insensitive comparison
  - Smart array field matching (matches fields both with and without array prefixes)
- **Advanced Features**:
  - **JSON Validation**: Comprehensive validation for syntax errors, structure issues, and data quality
  - Batch processing of multiple JSON files
  - Per-file detailed field-level logging
  - Special character detection and validation
  - Null/empty category detection
  - Multi-record JSON file support
  - Memory-optimized processing for large datasets
- **Comprehensive Logging**:
  - Detailed per-file field analysis showing exactly which fields are missing in each JSON file
  - Per-file summary statistics
  - Unique fields summary across all files
  - Special characters log
  - Error log with detailed information
- **Visual Comparison**: 
  - Color-coded results (green for matches, red/yellow for mismatches)
  - Detailed summary statistics
  - Export results to multiple formats
- **User-Friendly GUI**: Built with tkinter for easy desktop use

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Note: For Oracle database support, you may need to install Oracle Instant Client separately.

3. **Run the application**:
   ```bash
   python field_mapper.py
   ```

## Usage

### Step 1: Select Annexure

1. Select an **Annexure** from the dropdown (e.g., "Theme Database", "Biomarker Genomic/Molecular Alteration Module")
2. Click **"Load Annexure Fields"** to load the predefined field schema
3. The tool will display the number of fields loaded and their status

### Step 2: Select JSON Folder

1. Click **"Browse Folder"** in the JSON Folder Configuration section
2. Select a folder containing your JSON files
   - The tool will **recursively scan all subfolders** and find all JSON files
   - Works with any folder structure (direct files, nested subfolders, or mixed)
3. You'll see a confirmation showing how many JSON files were found (e.g., "15 in root, 45 in subfolders")

### Step 3: Validate JSON (Optional but Recommended)

1. Click **"Validate JSON"** to check all JSON files for errors
2. Review validation results:
   - Syntax errors and their locations
   - Structure issues and warnings
   - Data quality problems
3. Fix any invalid files before proceeding
4. See [JSON_VALIDATOR_GUIDE.md](JSON_VALIDATOR_GUIDE.md) for detailed validation documentation

### Step 4: Compare Fields

1. Click **"Compare Fields"** to start the comparison
2. The tool will process all JSON files and compare them against the selected annexure
3. View real-time progress in the Processing Status section
4. Results appear in the **Comparison Results** tab:
   - **Matched fields**: Green background
   - **Fields missing in JSON**: Red background (fields in annexure but not in JSON)
   - **Fields not in annexure**: Yellow background (fields in JSON but not in annexure)
5. Check the **Summary** tab for detailed statistics

### Step 5: View Additional Results

Use the action buttons at the bottom:

- **Validate JSON**: Check JSON files for syntax and structure errors
- **Show Unmatched Fields**: Filter to show only mismatched fields
- **Export Results**: Save comparison results to a file
- **Export Fields Not Found Under Annexure**: Export only JSON fields not in annexure
- **Show Special Characters**: View fields containing special characters
- **View Logs**: Open detailed log files showing per-file field analysis
- **Clear All**: Reset the tool for a new comparison

### Understanding the Logs

The field matching log (in the `logs/` folder) contains three sections:

1. **DETAILED PER-FILE FIELD ANALYSIS** (beginning of log):
   - Shows **exactly which fields** are missing for **each specific JSON file**
   - Search for your filename (Ctrl+F) to find its details
   
2. **PER-FILE SUMMARY STATISTICS** (middle of log):
   - Shows counts only (e.g., "Matched: 13, Missing in JSON: 16")
   
3. **UNIQUE UNMATCHED FIELDS** (end of log):
   - Lists all unique fields with issues across all files combined

## JSON File Structure Support

The tool supports various JSON structures and automatically handles complex nesting:

### Simple Object
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Nested Object
```json
{
  "data": {
    "user": {
      "name": "John",
      "email": "john@example.com"
    }
  }
}
```

### Array of Objects
```json
{
  "items": [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"}
  ]
}
```

### Nested Arrays (Advanced)
```json
{
  "BIOPATHWAY_PRODUCT_DETAILS": [
    {
      "BIOPATHWAYPRODUCT:ENZYME": "CYP2C19",
      "BIOPATHWAYPRODUCT:REACTION_TYPE": "Hydroxylation"
    }
  ]
}
```

**Smart Array Field Matching**: The tool extracts fields from nested arrays in two ways:
- With full path: `BIOPATHWAY_PRODUCT_DETAILS.BIOPATHWAYPRODUCT:ENZYME`
- Without prefix: `BIOPATHWAYPRODUCT:ENZYME`

This allows fields inside arrays to match against your annexure configuration regardless of whether the array parent name is included.

## Configuration

### Annexure Configuration (`database_config.py`)

Add or modify annexure schemas:

```python
DATABASE_FIELDS = {
    "Your Annexure Name": [
        "FIELD_1",
        "FIELD_2",
        "NESTED_FIELD",
        # ... more fields
    ]
}
```

### Comparison Settings (`field_comparator.py`)

- `case_sensitive`: Set to `True` for case-sensitive matching
- `fuzzy_match`: Set to `False` to disable fuzzy matching
- `similarity_threshold`: Adjust threshold (0.0 to 1.0) for fuzzy matching

### Special Character Configuration

Configure which fields should have special characters removed during processing in `database_config.py`:

```python
SPECIAL_CHAR_REMOVAL = {
    "Theme Database": {
        "FIELD_NAME": ['®', '™'],  # Characters to remove from this field
    }
}
```

## Supported Annexures

The tool comes pre-configured with 11 annexures:

1. **Theme Database** - Biotransformation pathways and drug metabolism
2. **Biomarker Genomic/Molecular Alteration Module**
3. **Investigational and Approved Therapeutics Module**
4. **Clinical Trials Module**
5. **Protein Degradation Database (Proximers Database)**
6. **Spectra Database**
7. **Cellular Assay Database**
8. **Toxicology Database**
9. **ADME Properties Module**
10. **Liceptor Database**
11. **Investigational and Approved Therapeutic Drug Targets Module**

## Troubleshooting

### Common Issues

**Q: Why are fields showing as "not found under annexure" when they exist in my JSON?**

A: This usually happens with nested array fields. The latest version includes smart array field matching that extracts fields both with and without array prefixes. Make sure you're using the updated version.

**Q: How do I know which specific fields are missing in each JSON file?**

A: Open the field matching log file in the `logs/` folder. The beginning of the log contains a "DETAILED PER-FILE FIELD ANALYSIS" section showing exactly which fields are missing for each file. Use Ctrl+F to search for your filename.

**Q: The tool says "No JSON files found" but I have JSON files in my folder**

A: Check that:
- Files have a `.json` extension
- You've selected the correct folder
- The tool now recursively scans subfolders, so it should find files anywhere in the folder tree

**Q: Fields with special characters (®, ™, etc.) are causing issues**

A: Configure special character removal in `database_config.py`. The tool can automatically clean specific characters from specified fields during comparison.

### Performance Tips

- For folders with 100+ JSON files, the tool will prompt for confirmation before processing
- Large files are processed in batches to optimize memory usage
- Progress is shown in real-time during processing

## File Structure

```
.
├── field_mapper.py          # Main application GUI
├── database_config.py       # Annexure configurations and field definitions
├── json_parser.py           # JSON file parsing and field extraction
├── json_validator.py        # JSON validation module (NEW)
├── field_comparator.py      # Field comparison logic
├── field_loader.py          # Field loading utilities
├── document_parser.py       # Word document parsing (legacy support)
├── requirements.txt         # Python dependencies
├── logs/                    # Generated log files
│   ├── *_field_matching_*.log     # Detailed field matching results
│   ├── *_special_chars_*.log      # Special character validation
│   ├── *_errors_*.log             # Error logs
│   └── json_validation_*.log      # JSON validation reports (NEW)
├── README.md                # This file
└── JSON_VALIDATOR_GUIDE.md  # JSON validator documentation (NEW)
```

## License

This tool is provided as-is for field mapping and comparison purposes.

## Support

For issues or questions, please check:
1. Document format and structure
2. JSON file format validity
3. Required Python packages are installed (python-docx)

## Recent Enhancements

### December 2024
- ✅ **JSON Validator**: Comprehensive validation for syntax errors, structure issues, and data quality
  - Syntax validation with error location and suggestions
  - Structure validation (nesting depth, consistency checks)
  - Data quality checks (null values, empty strings, file size)
  - Batch validation with detailed reports
  - Optional JSON schema validation support
  - See [JSON_VALIDATOR_GUIDE.md](JSON_VALIDATOR_GUIDE.md) for details

### November 2024
- ✅ **Removed JSON Path Input**: Simplified UI by removing the optional JSON path field
- ✅ **Recursive Folder Scanning**: Automatically finds JSON files in all subfolders
- ✅ **Smart Array Field Matching**: Extracts nested array fields with and without parent prefixes
- ✅ **Detailed Per-File Logging**: Shows exactly which fields are missing in each JSON file
- ✅ **Enhanced Log Structure**: Three-section logs (detailed analysis, statistics, unique summary)
- ✅ **Improved Field Extraction**: Better handling of deeply nested structures
- ✅ **Memory Optimization**: Batch processing for large file sets

## Future Enhancements

- Field type comparison and validation
- Export to Excel format
- Command-line interface for automation
- Custom annexure import/export
- Field mapping suggestions using AI
- Multi-annexure comparison mode

