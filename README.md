# Field Mapper - Document to JSON Comparison Tool

A desktop application built with Python that compares field names from database tables (extracted from Word documents) with fields in JSON files. This tool helps identify matching and mismatched fields between your database schema documentation and JSON data structures.

## Features

- **Document Parsing**: Extract database and table field information from Word (.docx) documents
- **JSON Field Extraction**: Automatically extract field names from JSON files, including nested structures
- **Intelligent Matching**: 
  - Exact field name matching
  - Fuzzy matching for similar field names (configurable similarity threshold)
  - Case-insensitive comparison option
- **Visual Comparison**: 
  - Color-coded results (green for matches, red/yellow for mismatches)
  - Detailed summary statistics
  - Export results to JSON or text files
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

### Loading Database Fields from Document

1. Click **"Browse"** to select your Word document (.docx file)
2. Click **"Parse Document"** to extract database and table information
3. Select a **Database** from the dropdown (automatically populated after parsing)
4. Select a **Table** from the dropdown (automatically populated based on selected database)
5. Click **"Load Fields from Document"** to load field names for the selected table

### Loading JSON Fields

1. Click **"Browse"** to select a JSON file
2. (Optional) Enter a **JSON Path** if you want to extract fields from a specific section:
   - Example: `data.fields` to extract from `{"data": {"fields": {...}}}`
   - Example: `root.items` to extract from nested structure
3. Click **"Load JSON Fields"** to extract field names

### Comparing Fields

1. After loading both database fields and JSON fields, click **"Compare Fields"**
2. View results in the **Comparison Results** tab:
   - **Matched fields**: Green background
   - **Unmatched DB fields**: Red background (fields in database but not in JSON)
   - **Unmatched JSON fields**: Yellow background (fields in JSON but not in database)
3. Check the **Summary** tab for detailed statistics

### Exporting Results

Click **"Export Results"** to save comparison results to a JSON or text file.

## JSON File Structure Support

The tool supports various JSON structures:

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

Use the **JSON Path** field to navigate to specific sections:
- For nested objects: `data.user`
- For arrays: The tool automatically extracts fields from the first array element

## Configuration

You can modify comparison behavior by editing `field_comparator.py`:

- `case_sensitive`: Set to `True` for case-sensitive matching
- `fuzzy_match`: Set to `False` to disable fuzzy matching
- `similarity_threshold`: Adjust threshold (0.0 to 1.0) for fuzzy matching

## Document Format

The tool expects Word documents (.docx) containing database and table field information. The parser looks for:

- **Database names**: Patterns like "Database: name", "DB: name", or "Database Name: name"
- **Table names**: Patterns like "Table: name", "Table Name: name", or "Fields for: name"
- **Field names**: Lists of field names, either in:
  - Comma-separated lists
  - Bullet points
  - Table format (with a "Field" or "Column" header)

### Example Document Structure

```
Database: MyDatabase

Table: Users
Fields: id, name, email, created_at, updated_at

Table: Orders
Fields: order_id, user_id, product_name, quantity, price, order_date
```

## Troubleshooting

### Document Parsing Issues

- **No databases found**: Ensure your document contains clear database and table names
- **No fields found**: Check that field names are listed clearly after table names
- **Format issues**: The parser looks for common patterns. If your document uses a different format, you may need to adjust the document structure or modify `document_parser.py`

### JSON Parsing Issues

- Ensure JSON file is valid (use a JSON validator)
- For nested structures, use the JSON Path field to navigate
- Large JSON files may take time to process

## File Structure

```
.
├── field_mapper.py          # Main application GUI
├── document_parser.py      # Word document parsing and field extraction
├── json_parser.py          # JSON file parsing and field extraction
├── field_comparator.py     # Field comparison logic
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

This tool is provided as-is for field mapping and comparison purposes.

## Support

For issues or questions, please check:
1. Document format and structure
2. JSON file format validity
3. Required Python packages are installed (python-docx)

## Future Enhancements

- Support for multiple tables comparison
- Batch JSON file processing
- Field type comparison
- Mapping configuration save/load
- Command-line interface option
- Report generation (PDF/Excel)

