"""
Field Mapper - Desktop Tool
Compares database table fields with JSON file fields
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
import glob
import logging
import threading
import subprocess
import platform
from typing import Dict, List, Set, Tuple
from datetime import datetime

# Setup logging with file handler
def setup_logging(database_name: str = ""):
    """Setup logging - only creates special characters and field matching log files"""
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create log filenames with database name and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize database name for filename (remove invalid characters)
    safe_db_name = database_name.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('(', '_').replace(')', '_') if database_name else "default"
    
    # Get absolute path for logs directory
    logs_dir_abs = os.path.abspath(logs_dir)
    
    # Final logs (complete summary at the end)
    log_filename_special_chars_final = os.path.join(logs_dir_abs, f"{safe_db_name}_special_chars_{timestamp}.log")
    log_filename_field_matching_final = os.path.join(logs_dir_abs, f"{safe_db_name}_field_matching_{timestamp}.log")
    
    # Error log file
    log_filename_errors = os.path.join(logs_dir_abs, f"{safe_db_name}_errors_{timestamp}.log")
    
    # Log the log file locations
    logger.info(f"Log files will be saved to: {logs_dir_abs}")
    logger.info(f"  - Special chars: {log_filename_special_chars_final}")
    logger.info(f"  - Field matching: {log_filename_field_matching_final}")
    logger.info(f"  - Errors: {log_filename_errors}")
    
    # Special characters log - write final summary only
    class SpecialCharsFileWriter:
        """Write special characters logs - final summary only"""
        def __init__(self, final_filename):
            self.final_filename = final_filename
            # Data for final summary log
            self.db_fields = {}
            self.json_fields = {}
        
        def write_json_field(self, field_name, special_chars, file_name, line_num, sample_value):
            """Store JSON field data for final summary log"""
            # Store for final summary
            if field_name not in self.json_fields:
                self.json_fields[field_name] = {
                    'special_chars': set(),
                    'sample_value': sample_value,
                    'files': []
                }
            self.json_fields[field_name]['special_chars'].update(special_chars)
            if not self.json_fields[field_name]['sample_value']:
                self.json_fields[field_name]['sample_value'] = sample_value
            if file_name:
                self.json_fields[field_name]['files'].append((file_name, line_num))
        
        def write_db_field(self, field_name, special_chars):
            """Store DB field data for final summary log"""
            # Store for final summary
            if field_name not in self.db_fields:
                self.db_fields[field_name] = set()
            self.db_fields[field_name].update(special_chars)
        
        def finalize(self):
            """Write final summary log"""
            # Write final summary log
            final_file = open(self.final_filename, 'w', encoding='utf-8')
            final_file.write("SPECIAL CHARACTER VALIDATION\n")
            final_file.write("="*50 + "\n")
            final_file.write("Fields with special characters in VALUES (excluding HELM, MolStructure, SMILES fields):\n\n")
            
            if self.db_fields:
                unique_db_fields = sorted(self.db_fields.keys())
                final_file.write(f"Annexure Fields ({len(unique_db_fields)}):\n")
                for field in unique_db_fields:
                    chars_list = sorted(list(self.db_fields[field]))
                    chars_str = ', '.join([f"'{c}'" for c in chars_list])
                    final_file.write(f"  - {field}: special characters [{chars_str}]\n")
            
            if self.json_fields:
                unique_json_fields = sorted(self.json_fields.keys())
                final_file.write(f"\nJSON Fields ({len(unique_json_fields)}):\n")
                for field in unique_json_fields:
                    info = self.json_fields[field]
                    chars_list = sorted(list(info['special_chars']))
                    chars_str = ', '.join([f"'{c}'" for c in chars_list])
                    sample = info['sample_value']
                    
                    file_info_parts = []
                    for file_name, line_num in info['files']:
                        if line_num:
                            file_info_parts.append(f"{file_name}:{line_num}")
                        else:
                            file_info_parts.append(file_name)
                    file_info = ", ".join(file_info_parts) if file_info_parts else ""
                    
                    if sample:
                        sample_display = sample[:80] + '...' if len(sample) > 80 else sample
                        if file_info:
                            final_file.write(f"  - {field}: special characters [{chars_str}], file: {file_info}, sample value: \"{sample_display}\"\n")
                        else:
                            final_file.write(f"  - {field}: special characters [{chars_str}], sample value: \"{sample_display}\"\n")
                    else:
                        if file_info:
                            final_file.write(f"  - {field}: special characters [{chars_str}], file: {file_info}\n")
                        else:
                            final_file.write(f"  - {field}: special characters [{chars_str}]\n")
            
            if not self.db_fields and not self.json_fields:
                final_file.write("No special characters found in field values.\n\n")
            
            final_file.close()
    
    # Error log writer - writes all errors to a separate file
    class ErrorLogWriter:
        """Write errors to a separate error log file"""
        def __init__(self, error_filename):
            self.error_filename = error_filename
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(error_filename), exist_ok=True)
                self.error_file = open(error_filename, 'w', encoding='utf-8')
                self.error_file.write("ERROR LOG\n")
                self.error_file.write("="*50 + "\n")
                self.error_file.write(f"Database: {database_name}\n")
                self.error_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.error_file.write("="*50 + "\n\n")
                self.error_file.flush()
                logger.info(f"Created error log: {error_filename}")
            except Exception as e:
                logger.error(f"Failed to create error log file {error_filename}: {e}", exc_info=True)
                self.error_file = None
        
        def write_error(self, error_message, exc_info=None, file_path=None, line_number=None):
            """Write an error to the error log file"""
            if self.error_file is None:
                return
            
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.error_file.write(f"[{timestamp}] ERROR\n")
                
                if file_path:
                    if line_number:
                        self.error_file.write(f"Location: {file_path}:{line_number}\n")
                    else:
                        self.error_file.write(f"Location: {file_path}\n")
                
                self.error_file.write(f"Message: {error_message}\n")
                
                if exc_info:
                    import traceback
                    if isinstance(exc_info, Exception):
                        self.error_file.write(f"Exception: {type(exc_info).__name__}: {str(exc_info)}\n")
                        self.error_file.write("Traceback:\n")
                        self.error_file.write(''.join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)))
                    elif exc_info is True:
                        # Get current exception
                        import sys
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        if exc_type:
                            self.error_file.write(f"Exception: {exc_type.__name__}: {str(exc_value)}\n")
                            self.error_file.write("Traceback:\n")
                            self.error_file.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                
                self.error_file.write("-"*50 + "\n\n")
                self.error_file.flush()
            except Exception as e:
                # Don't log errors about error logging to avoid recursion
                print(f"Failed to write to error log: {e}")
        
        def write_warning(self, warning_message, file_path=None):
            """Write a warning to the error log file"""
            if self.error_file is None:
                return
            
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.error_file.write(f"[{timestamp}] WARNING\n")
                
                if file_path:
                    self.error_file.write(f"Location: {file_path}\n")
                
                self.error_file.write(f"Message: {warning_message}\n")
                self.error_file.write("-"*50 + "\n\n")
                self.error_file.flush()
            except Exception as e:
                print(f"Failed to write warning to error log: {e}")
        
        def close(self):
            """Close the error log file"""
            if self.error_file:
                try:
                    self.error_file.write(f"\nError log closed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    self.error_file.close()
                except:
                    pass
    
    # Create error log writer instance
    error_log_writer = ErrorLogWriter(log_filename_errors)
    
    # Create special chars writer instance (will be stored globally)
    special_chars_writer = SpecialCharsFileWriter(log_filename_special_chars_final)
    
    # Field matching log - write final summary only
    class FieldMatchingFileWriter:
        """Write field matching logs - detailed per-file field-level logging"""
        def __init__(self, final_filename):
            self.final_filename = final_filename
            # Data for final summary log
            self.file_results = []
            self.unmatched_db_fields = []
            self.unmatched_json_fields = []
            self.total_matched = 0
            self.total_unmatched_db = 0
            self.total_unmatched_json = 0
            # Per-file field tracking for detailed logging
            self.file_field_details = {}  # {file_name: {'missing_in_json': [], 'not_in_annexure': []}}
            self.current_file = None
        
        def write_comparison_summary(self, matched, unmatched_db, unmatched_json):
            """Store totals for final log"""
            self.total_matched = matched
            self.total_unmatched_db = unmatched_db
            self.total_unmatched_json = unmatched_json
        
        def write_unmatched_db_field(self, field_name, match_type):
            """Store unmatched DB field data for final summary log"""
            # Store for final summary
            self.unmatched_db_fields.append({'field_name': field_name, 'match_type': match_type})
            # Store for current file if set
            if self.current_file:
                if self.current_file not in self.file_field_details:
                    self.file_field_details[self.current_file] = {'missing_in_json': [], 'not_in_annexure': []}
                self.file_field_details[self.current_file]['missing_in_json'].append({'field_name': field_name, 'match_type': match_type})
        
        def write_unmatched_json_field(self, field_name, match_type):
            """Store unmatched JSON field data for final summary log"""
            # Store for final summary
            self.unmatched_json_fields.append({'field_name': field_name, 'match_type': match_type})
            # Store for current file if set
            if self.current_file:
                if self.current_file not in self.file_field_details:
                    self.file_field_details[self.current_file] = {'missing_in_json': [], 'not_in_annexure': []}
                self.file_field_details[self.current_file]['not_in_annexure'].append({'field_name': field_name, 'match_type': match_type})
        
        def write_file_result(self, file_name, matched, unmatched_db, unmatched_json):
            """Store per-file result data for final summary log"""
            # Store for final summary
            self.file_results.append((file_name, matched, unmatched_db, unmatched_json))
            # Set current file for field tracking
            self.current_file = file_name
        
        def finalize(self):
            """Write final summary log with detailed per-file field information"""
            # Write final summary log
            final_file = open(self.final_filename, 'w', encoding='utf-8')
            final_file.write("FIELD COMPARISON SUMMARY\n")
            final_file.write("="*80 + "\n\n")
            final_file.write("OVERALL COMPARISON RESULTS:\n")
            final_file.write("-"*80 + "\n")
            final_file.write(f"Matched Fields: {self.total_matched}\n")
            final_file.write(f"Missing in JSON: {self.total_unmatched_db}\n")
            final_file.write(f"Not found under annexure: {self.total_unmatched_json}\n")
            final_file.write(f"Total Compared: {self.total_matched + self.total_unmatched_db + self.total_unmatched_json}\n\n")
            
            # DETAILED PER-FILE FIELD-LEVEL LOGGING
            if self.file_field_details:
                final_file.write("\n")
                final_file.write("="*80 + "\n")
                final_file.write("DETAILED PER-FILE FIELD ANALYSIS\n")
                final_file.write("="*80 + "\n\n")
                
                for file_name in sorted(self.file_field_details.keys()):
                    details = self.file_field_details[file_name]
                    missing_in_json = details.get('missing_in_json', [])
                    not_in_annexure = details.get('not_in_annexure', [])
                    
                    final_file.write("-"*80 + "\n")
                    final_file.write(f"FILE: {file_name}\n")
                    final_file.write("-"*80 + "\n")
                    
                    if missing_in_json:
                        final_file.write(f"\n  Fields Missing in JSON ({len(missing_in_json)}):\n")
                        for field_info in missing_in_json:
                            final_file.write(f"    - {field_info['field_name']}: {field_info['match_type']}\n")
                    else:
                        final_file.write(f"\n  Fields Missing in JSON: None\n")
                    
                    if not_in_annexure:
                        final_file.write(f"\n  Fields Not Found Under Annexure ({len(not_in_annexure)}):\n")
                        for field_info in not_in_annexure:
                            final_file.write(f"    - {field_info['field_name']}: {field_info['match_type']}\n")
                    else:
                        final_file.write(f"\n  Fields Not Found Under Annexure: None\n")
                    
                    final_file.write("\n")
            
            # SUMMARY STATISTICS
            if self.file_results:
                final_file.write("\n")
                final_file.write("="*80 + "\n")
                final_file.write("PER-FILE SUMMARY STATISTICS\n")
                final_file.write("="*80 + "\n\n")
                for file_name, matched, unmatched_db, unmatched_json in self.file_results:
                    final_file.write(f"{file_name}\n")
                    final_file.write(f"  Matched: {matched}, Missing in JSON: {unmatched_db}, Not in Annexure: {unmatched_json}\n\n")
            
            # UNIQUE FIELDS SUMMARY (across all files)
            if self.unmatched_db_fields or self.unmatched_json_fields:
                final_file.write("\n")
                final_file.write("="*80 + "\n")
                final_file.write("UNIQUE UNMATCHED FIELDS (ACROSS ALL FILES)\n")
                final_file.write("="*80 + "\n\n")
                
                if self.unmatched_db_fields:
                    unique_db = {}
                    for field_info in self.unmatched_db_fields:
                        field_name = field_info['field_name']
                        if field_name not in unique_db:
                            unique_db[field_name] = field_info['match_type']
                    
                    final_file.write(f"Missing in JSON Fields ({len(unique_db)}):\n")
                    for field_name, match_type in sorted(unique_db.items()):
                        final_file.write(f"  - {field_name}: {match_type}\n")
                
                if self.unmatched_json_fields:
                    unique_json = {}
                    for field_info in self.unmatched_json_fields:
                        field_name = field_info['field_name']
                        if field_name not in unique_json:
                            unique_json[field_name] = field_info['match_type']
                    
                    final_file.write(f"\nFields not found under annexure ({len(unique_json)}):\n")
                    for field_name, match_type in sorted(unique_json.items()):
                        final_file.write(f"  - {field_name}: {match_type}\n")
            
            final_file.close()
    
    # Create field matching writer instance
    field_matching_writer = FieldMatchingFileWriter(log_filename_field_matching_final)
    
    return {
        'special_chars': log_filename_special_chars_final,
        'field_matching': log_filename_field_matching_final,
        'errors': log_filename_errors,
        'special_chars_writer': special_chars_writer,
        'field_matching_writer': field_matching_writer,
        'error_log_writer': error_log_writer
    }

# Initialize basic logging (without file handlers, will be set up when comparison starts)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]  # Only console for now
    )
logger = logging.getLogger(__name__)

# Handle bundled executable (PyInstaller)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from document_parser import DocumentParser
from field_loader import FieldLoader
from json_parser import JSONParser
from field_comparator import FieldComparator
from json_validator import JSONValidator


class FieldMapperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Field Mapper - Document to JSON Comparison Tool")
        self.root.geometry("1200x800")
        
        # Initialize components
        self.document_parser = DocumentParser()
        self.field_loader = FieldLoader()
        self.json_parser = JSONParser()
        self.comparator = FieldComparator()
        self.json_validator = JSONValidator()
        
        # Data storage
        self.db_fields = {}  # Format: {'database_name.table_name': [fields]}
        self.all_db_fields = []  # All fields from all databases/tables combined
        self.json_fields = {}  # Loaded JSON files
        self.json_folder = None  # Folder path for batch processing
        self.json_files_list = []  # List of JSON files in folder
        self.comparison_results = {}
        self.parsed_document_data = {}
        self.loader_data = {}
        self.record_unmatched_info = {}  # Store per-record unmatched field info: {file_path: {record_idx: {unmatched_json: [], unmatched_db: []}}}
        self.fields_with_special_chars = {'db': [], 'json': []}  # Store fields with special characters
        self.current_log_files = {}  # Store current log file paths (will be set when comparison starts)
        self.special_chars_writer = None  # Special chars log writer (will be set when comparison starts)
        self.field_matching_writer = None  # Field matching log writer (will be set when comparison starts)
        self.error_log_writer = None  # Error log writer (will be set when comparison starts)
        self.logs_dir = "logs"  # Logs directory
        
        self.create_widgets()
        self.auto_load_config()
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Field Mapper Tool", 
                                font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Annexure Selection Section
        db_selection_frame = ttk.LabelFrame(main_frame, text="Annexure Fields Selection", padding="10")
        db_selection_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        db_selection_frame.columnconfigure(1, weight=1)
        
        ttk.Label(db_selection_frame, text="Select Annexure:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.database_var = tk.StringVar()
        self.database_combo = ttk.Combobox(db_selection_frame, textvariable=self.database_var, 
                                           state="readonly", width=40)
        self.database_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.database_combo.bind('<<ComboboxSelected>>', self.on_database_selected)
        
        ttk.Button(db_selection_frame, text="Load Annexure Fields", 
                 command=self.load_database_fields).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(db_selection_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.db_status_var = tk.StringVar(value="Please select an annexure and click 'Load Annexure Fields'")
        status_label = ttk.Label(db_selection_frame, textvariable=self.db_status_var, 
                                 foreground="blue")
        status_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(db_selection_frame, text="Total Fields:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.total_fields_var = tk.StringVar(value="0")
        ttk.Label(db_selection_frame, textvariable=self.total_fields_var, 
                 font=("Arial", 10, "bold")).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # JSON Section
        json_frame = ttk.LabelFrame(main_frame, text="JSON Folder Configuration", padding="10")
        json_frame.grid(row=1, column=3, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        json_frame.columnconfigure(1, weight=1)
        
        ttk.Label(json_frame, text="JSON Folder:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.json_folder_var = tk.StringVar()
        json_folder_entry = ttk.Entry(json_frame, textvariable=self.json_folder_var, width=40, state="readonly")
        json_folder_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(json_frame, text="Browse Folder", 
                  command=self.browse_json_folder).grid(row=0, column=2, padx=5, pady=5)
        
        # Results Section
        results_frame = ttk.LabelFrame(main_frame, text="Comparison Results", padding="10")
        results_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Comparison Results Tab
        comparison_frame = ttk.Frame(self.notebook)
        self.notebook.add(comparison_frame, text="Comparison Results")
        
        # Treeview for results
        tree_frame = ttk.Frame(comparison_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Results Tree
        self.results_tree = ttk.Treeview(tree_frame, 
                                        columns=("Status", "DB Field", "JSON Field", "Match Type"),
                                        show="tree headings",
                                        yscrollcommand=tree_scroll_y.set,
                                        xscrollcommand=tree_scroll_x.set)
        self.results_tree.heading("#0", text="Field")
        self.results_tree.heading("Status", text="Status")
        self.results_tree.heading("DB Field", text="Annexure Field")
        self.results_tree.heading("JSON Field", text="JSON Field")
        self.results_tree.heading("Match Type", text="Match Type")
        
        self.results_tree.column("#0", width=200)
        self.results_tree.column("Status", width=100)
        self.results_tree.column("DB Field", width=200)
        self.results_tree.column("JSON Field", width=200)
        self.results_tree.column("Match Type", width=150)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.config(command=self.results_tree.yview)
        tree_scroll_x.config(command=self.results_tree.xview)
        
        # Summary Tab
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="Summary")
        
        self.summary_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, height=20)
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Processing Status", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        progress_frame.columnconfigure(1, weight=1)
        
        ttk.Label(progress_frame, text="Status:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.progress_status_var = tk.StringVar(value="Ready")
        progress_status_label = ttk.Label(progress_frame, textvariable=self.progress_status_var, 
                                         foreground="blue", font=("Arial", 9))
        progress_status_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.progress_bar.grid_remove()  # Hide initially
        
        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=5, pady=10)
        
        self.validate_json_button = ttk.Button(button_frame, text="Validate JSON", 
                  command=self.validate_json_files)
        self.validate_json_button.pack(side=tk.LEFT, padx=5)
        
        self.compare_button = ttk.Button(button_frame, text="Compare Fields", 
                  command=self.compare_fields)
        self.compare_button.pack(side=tk.LEFT, padx=5)
        
        self.show_unmatched_button = ttk.Button(button_frame, text="Show Unmatched Fields", 
                  command=self.show_unmatched_fields)
        self.show_unmatched_button.pack(side=tk.LEFT, padx=5)
        
        self.export_button = ttk.Button(button_frame, text="Export Results", 
                  command=self.export_results)
        self.export_button.pack(side=tk.LEFT, padx=5)
        
        self.export_unmatched_json_button = ttk.Button(button_frame, text="Export Fields Not Found Under Annexure", 
                  command=self.export_unmatched_json_fields)
        self.export_unmatched_json_button.pack(side=tk.LEFT, padx=5)
        
        self.show_special_chars_button = ttk.Button(button_frame, text="Show Special Characters", 
                  command=self.show_special_characters)
        self.show_special_chars_button.pack(side=tk.LEFT, padx=5)
        
        self.view_logs_button = ttk.Button(button_frame, text="View Logs", 
                  command=self.show_log_menu)
        self.view_logs_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="Clear All", 
                  command=self.clear_all)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Processing flag
        self.is_processing = False
        
    def auto_load_config(self):
        """Automatically load database list from config file on startup"""
        try:
            # Try to find config file - use resource_path for PyInstaller compatibility
            config_file = resource_path("database_config.py")
            
            # If bundled file doesn't exist, try current directory (for development)
            if not os.path.exists(config_file):
                config_file = "database_config.py"
            
            # If still not found, try executable directory
            if not os.path.exists(config_file):
                if getattr(sys, 'frozen', False):
                    exe_dir = os.path.dirname(sys.executable)
                else:
                    exe_dir = os.path.dirname(os.path.abspath(__file__))
                config_file = os.path.join(exe_dir, "database_config.py")
            
            if not os.path.exists(config_file):
                self.db_status_var.set(f"Error: Config file not found")
                self.total_fields_var.set("0")
                messagebox.showwarning("Config File Not Found", 
                                      f"Could not find database_config.py\n\n"
                                      f"Please ensure database_config.py is in the same folder as the application.")
                return
            
            # Load from config file (just to get database list)
            self.field_loader.load_from_config_file(config_file)
            self.loader_data = self.field_loader.get_all_data()
            
            # Populate database dropdown
            databases = self.field_loader.get_databases()
            self.database_combo['values'] = databases
            
            if databases:
                # Select first database by default
                self.database_var.set(databases[0])
                self.db_status_var.set(f"Found {len(databases)} annexure(s). Select an annexure and click 'Load Annexure Fields'")
            else:
                self.db_status_var.set("No annexures found in config file")
            
            logger.info(f"Loaded {len(databases)} databases from {config_file}")
            
        except Exception as e:
            error_msg = f"Failed to load config: {str(e)}"
            self.db_status_var.set(error_msg)
            self.total_fields_var.set("0")
            logger.error(error_msg)
            messagebox.showerror("Error Loading Config", error_msg)
    
    def on_database_selected(self, event=None):
        """Handle database selection change"""
        # Just update status, don't load fields yet
        database = self.database_var.get()
        if database:
            self.db_status_var.set(f"Annexure '{database}' selected. Click 'Load Annexure Fields' to load fields.")
    
    def load_database_fields(self):
        """Load all fields from the selected database (all tables combined)"""
        try:
            database = self.database_var.get()
            
            if not database:
                messagebox.showerror("Error", "Please select an annexure first")
                return
            
            # Load ALL fields from the selected database (handles both simple and table structures)
            self.all_db_fields = []
            self.db_fields = {}  # Clear previous
            
            # Get all fields from database (no table name = gets all fields)
            fields = self.field_loader.get_fields(database)
            
            # Also get category names (tables) from database for comparison
            # Note: Only databases with dict structure have categories (e.g., "Pharmacokinetic Database")
            # Databases with list structure (e.g., "Liceptor Database") will return empty list
            # Category names in JSON should be compared against database categories when they exist
            categories = self.field_loader.get_tables(database)
            if categories:
                # Add category names to fields list so they can be compared
                # This only happens for databases that have categories defined
                fields.extend(categories)
            
            if not fields:
                messagebox.showwarning("Warning", 
                                      f"No fields found in annexure '{database}'")
                return
            
            # Store fields
            self.all_db_fields = fields
            self.db_fields[database] = fields
            
            # Update status
            total_count = len(self.all_db_fields)
            self.db_status_var.set(f"Loaded {total_count} fields from '{database}'")
            self.total_fields_var.set(str(total_count))
            
            messagebox.showinfo("Success", 
                               f"Loaded {total_count} fields from database '{database}'")
            
            logger.info(f"Loaded {total_count} fields from database '{database}'")
            
        except Exception as e:
            error_msg = f"Failed to load annexure fields: {str(e)}"
            self.db_status_var.set(error_msg)
            self.total_fields_var.set("0")
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def browse_json_folder(self):
        """Browse for folder containing JSON files and process them in batches (includes subfolders)"""
        folder = filedialog.askdirectory(title="Select Folder with JSON Files")
        if folder:
            try:
                # Find all JSON files in the folder and all subfolders recursively
                json_files = glob.glob(os.path.join(folder, "**", "*.json"), recursive=True)
                
                if not json_files:
                    messagebox.showwarning("No JSON Files", 
                                         f"No JSON files found in {folder} or its subfolders")
                    return
                
                # Count files in root vs subfolders for user information
                root_files = [f for f in json_files if os.path.dirname(f) == folder]
                subfolder_files = len(json_files) - len(root_files)
                
                location_info = f"{len(root_files)} in root"
                if subfolder_files > 0:
                    location_info += f", {subfolder_files} in subfolders"
                
                # Ask user for confirmation if many files
                if len(json_files) > 100:
                    response = messagebox.askyesno(
                        "Confirm Batch Load",
                        f"Found {len(json_files)} JSON files ({location_info}).\n"
                        f"This will process files during comparison to save memory. Continue?"
                    )
                    if not response:
                        return
                
                # Store folder path and file list instead of loading all at once
                self.json_folder = folder
                self.json_files_list = json_files
                self.json_fields = {}  # Clear previous loaded files
                self.json_folder_var.set(folder)  # Update UI display
                
                messagebox.showinfo("Folder Selected", 
                                   f"Selected folder with {len(json_files)} JSON files ({location_info}).\n"
                                   f"Files will be processed during comparison to optimize memory usage.")
                
                logger.info(f"Selected folder with {len(json_files)} JSON files ({location_info}): {folder}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to select folder: {str(e)}")
                logger.error(f"Folder selection error: {str(e)}")
    
    def set_processing_state(self, is_processing: bool):
        """Enable/disable UI elements during processing"""
        self.is_processing = is_processing
        state = tk.DISABLED if is_processing else tk.NORMAL
        
        self.compare_button.config(state=state)
        self.show_unmatched_button.config(state=state)
        self.export_button.config(state=state)
        if hasattr(self, 'export_unmatched_json_button'):
            self.export_unmatched_json_button.config(state=state)
        if hasattr(self, 'show_special_chars_button'):
            self.show_special_chars_button.config(state=state)
        # Log viewing buttons should remain enabled during processing
        # self.view_logs_button.config(state=state)
        # self.view_special_chars_logs_button.config(state=state)
        # self.view_field_matching_logs_button.config(state=state)
        self.clear_button.config(state=state)
        self.database_combo.config(state=state)
        
        if is_processing:
            self.progress_bar.grid()
            self.progress_status_var.set("Processing... Please wait")
        else:
            self.progress_bar.grid_remove()
            self.progress_status_var.set("Ready")
            self.progress_bar['value'] = 0
    
    def update_progress(self, current: int, total: int, message: str = ""):
        """Update progress bar and status (thread-safe)"""
        # Schedule UI update on main thread
        self.root.after(0, self._update_progress_ui, current, total, message)
    
    def _update_progress_ui(self, current: int, total: int, message: str = ""):
        """Internal method to update UI (runs on main thread)"""
        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar['value'] = current
            self.progress_bar['maximum'] = total
            # Format numbers with commas for readability (e.g., 200,000)
            if total > 1000:
                status_msg = f"Processing: {current:,}/{total:,} files ({percentage:.1f}%)"
            else:
                status_msg = f"Processing: {current}/{total} files ({percentage:.1f}%)"
            # Only append message if provided (for large datasets, message updates less frequently)
            if message:
                status_msg += f" - {message}"
            self.progress_status_var.set(status_msg)
        else:
            self.progress_status_var.set(message if message else "Processing...")
    
    def validate_json_files(self):
        """Validate JSON files for syntax and structure errors"""
        try:
            # Check if we have JSON files to validate
            if not self.json_files_list:
                messagebox.showerror("Error", 
                                    "Please select a JSON folder first")
                return
            
            # Confirm if there are many files
            total_files = len(self.json_files_list)
            if total_files > 100:
                response = messagebox.askyesno(
                    "Validate JSON Files",
                    f"You are about to validate {total_files} JSON files.\n\n"
                    "This may take some time. Continue?"
                )
                if not response:
                    return
            
            # Set processing state
            self.set_processing_state(True)
            
            # Initialize progress bar
            self.progress_bar['maximum'] = total_files
            self.progress_bar['value'] = 0
            self.update_progress(0, total_files, "Starting JSON validation...")
            
            # Start validation in background thread
            thread = threading.Thread(
                target=self._process_json_validation,
                args=(self.json_files_list,),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            self.set_processing_state(False)
            messagebox.showerror("Error", f"Failed to start validation: {str(e)}")
            logger.error(f"Validation start error: {str(e)}", exc_info=True)
    
    def _process_json_validation(self, json_files: List[str]):
        """Process JSON validation in background thread"""
        try:
            total_files = len(json_files)
            validation_results = {
                'total_files': total_files,
                'valid_files': 0,
                'invalid_files': 0,
                'files_with_warnings': 0,
                'details': []
            }
            
            # Validate each file
            for idx, json_file in enumerate(json_files, 1):
                try:
                    # Update progress
                    if idx % 10 == 0 or idx == total_files:
                        self.root.after(0, self.update_progress, idx, total_files, 
                                      f"Validating file {idx}/{total_files}...")
                    
                    # Validate file
                    result = self.json_validator.validate_file(json_file)
                    validation_results['details'].append(result)
                    
                    if result['valid']:
                        validation_results['valid_files'] += 1
                    else:
                        validation_results['invalid_files'] += 1
                    
                    if result['warnings']:
                        validation_results['files_with_warnings'] += 1
                    
                except Exception as e:
                    logger.error(f"Error validating {json_file}: {str(e)}")
                    validation_results['details'].append({
                        'valid': False,
                        'file': json_file,
                        'errors': [f"Validation error: {str(e)}"],
                        'warnings': [],
                        'info': {}
                    })
                    validation_results['invalid_files'] += 1
            
            # Generate and save report
            logs_dir = "logs"
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(logs_dir, f"json_validation_{timestamp}.log")
            
            report_text = self.json_validator.generate_report(validation_results, report_path)
            
            # Show results in UI
            self.root.after(0, self._show_validation_results, validation_results, report_path)
            
            # Complete
            self.root.after(0, self.set_processing_state, False)
            self.root.after(0, self.update_progress, total_files, total_files, "Validation complete!")
            
        except Exception as e:
            logger.error(f"Validation processing error: {str(e)}", exc_info=True)
            self.root.after(0, self.set_processing_state, False)
            self.root.after(0, messagebox.showerror, "Error", 
                          f"Validation failed: {str(e)}")
    
    def _show_validation_results(self, validation_results: Dict, report_path: str):
        """Show validation results in a popup window"""
        window = tk.Toplevel(self.root)
        window.title("JSON Validation Results")
        window.geometry("900x700")
        
        # Summary frame
        summary_frame = ttk.LabelFrame(window, text="Validation Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        summary_text = f"""
Total Files: {validation_results['total_files']}
Valid Files: {validation_results['valid_files']}
Invalid Files: {validation_results['invalid_files']}
Files with Warnings: {validation_results['files_with_warnings']}

Report saved to: {report_path}
        """
        
        summary_label = tk.Label(summary_frame, text=summary_text, justify=tk.LEFT, 
                                font=("Arial", 10))
        summary_label.pack()
        
        # Results frame with tabs
        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Invalid files tab
        if validation_results['invalid_files'] > 0:
            invalid_frame = ttk.Frame(notebook)
            notebook.add(invalid_frame, text=f"Invalid Files ({validation_results['invalid_files']})")
            
            invalid_text = scrolledtext.ScrolledText(invalid_frame, wrap=tk.WORD, 
                                                    font=("Courier New", 9))
            invalid_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            for detail in validation_results['details']:
                if not detail['valid']:
                    invalid_text.insert(tk.END, f"\n{'='*80}\n")
                    invalid_text.insert(tk.END, f"File: {os.path.basename(detail['file'])}\n")
                    invalid_text.insert(tk.END, f"Path: {detail['file']}\n\n")
                    
                    if detail['errors']:
                        invalid_text.insert(tk.END, "Errors:\n")
                        for error in detail['errors']:
                            invalid_text.insert(tk.END, f"  ✗ {error}\n")
                    
                    if detail.get('info', {}).get('suggestions'):
                        invalid_text.insert(tk.END, "\nSuggestions:\n")
                        for suggestion in detail['info']['suggestions']:
                            invalid_text.insert(tk.END, f"  → {suggestion}\n")
            
            invalid_text.config(state=tk.DISABLED)
        
        # Files with warnings tab
        if validation_results['files_with_warnings'] > 0:
            warnings_frame = ttk.Frame(notebook)
            notebook.add(warnings_frame, text=f"Warnings ({validation_results['files_with_warnings']})")
            
            warnings_text = scrolledtext.ScrolledText(warnings_frame, wrap=tk.WORD, 
                                                     font=("Courier New", 9))
            warnings_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            for detail in validation_results['details']:
                if detail['warnings']:
                    warnings_text.insert(tk.END, f"\n{'='*80}\n")
                    warnings_text.insert(tk.END, f"File: {os.path.basename(detail['file'])}\n")
                    warnings_text.insert(tk.END, f"Path: {detail['file']}\n\n")
                    
                    warnings_text.insert(tk.END, "Warnings:\n")
                    for warning in detail['warnings']:
                        warnings_text.insert(tk.END, f"  ⚠ {warning}\n")
                    
                    # Show additional info
                    if detail.get('info'):
                        info = detail['info']
                        if 'file_size_mb' in info:
                            warnings_text.insert(tk.END, f"\nFile Size: {info['file_size_mb']} MB\n")
                        if 'max_nesting_depth' in info:
                            warnings_text.insert(tk.END, f"Max Nesting Depth: {info['max_nesting_depth']}\n")
            
            warnings_text.config(state=tk.DISABLED)
        
        # Valid files tab
        valid_frame = ttk.Frame(notebook)
        notebook.add(valid_frame, text=f"Valid Files ({validation_results['valid_files']})")
        
        valid_text = scrolledtext.ScrolledText(valid_frame, wrap=tk.WORD, 
                                              font=("Courier New", 9))
        valid_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        for detail in validation_results['details']:
            if detail['valid'] and not detail['warnings']:
                valid_text.insert(tk.END, f"✓ {os.path.basename(detail['file'])}\n")
                if detail.get('info'):
                    info = detail['info']
                    if 'root_type' in info:
                        valid_text.insert(tk.END, f"  Type: {info['root_type']}")
                        if info['root_type'] == 'dict' and 'field_count' in info:
                            valid_text.insert(tk.END, f", Fields: {info['field_count']}")
                        elif info['root_type'] == 'list' and 'array_length' in info:
                            valid_text.insert(tk.END, f", Length: {info['array_length']}")
                        valid_text.insert(tk.END, "\n")
        
        valid_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Open Report File", 
                  command=lambda: self.open_file_in_default_app(report_path)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", 
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def compare_fields(self):
        """Compare database fields with JSON fields - starts background thread"""
        try:
            if self.is_processing:
                messagebox.showwarning("Processing", "Comparison is already in progress. Please wait.")
                return
            
            if not self.all_db_fields:
                messagebox.showerror("Error", 
                                   "No annexure fields loaded. Please check database_config.py")
                return
            
            # Check if we have JSON files to process
            if not self.json_files_list:
                messagebox.showerror("Error", 
                                    "Please select a JSON folder first")
                return
            
            json_files_to_process = self.json_files_list
            
            # Clear all previous results and logs before starting new comparison
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            self.summary_text.delete(1.0, tk.END)  # Clear summary
            self.record_unmatched_info = {}  # Clear per-record unmatched info
            self.fields_with_special_chars = {'db': [], 'json': []}  # Clear special character validation results
            self.comparison_results = {}  # Clear comparison results
            
            # Setup logging with database name for this comparison
            database = self.database_var.get()
            if database:
                log_files = setup_logging(database)
                self.current_log_files = log_files
                self.special_chars_writer = log_files.get('special_chars_writer')
                self.field_matching_writer = log_files.get('field_matching_writer')
                self.error_log_writer = log_files.get('error_log_writer')
                # Pass error_log_writer to the writer classes so they can log errors
                if self.special_chars_writer:
                    self.special_chars_writer.error_log_writer = self.error_log_writer
                if self.field_matching_writer:
                    self.field_matching_writer.error_log_writer = self.error_log_writer
                logger.info(f"Logging initialized for database '{database}'. Log files:")
                logger.info(f"  - Special characters: {log_files['special_chars']}")
                logger.info(f"  - Field matching: {log_files['field_matching']}")
                logger.info(f"  - Errors: {log_files['errors']}")
                
                # Set database-specific excluded keywords for special character validation
                try:
                    import database_config
                    if hasattr(database_config, 'EXCLUDED_KEYWORDS') and database in database_config.EXCLUDED_KEYWORDS:
                        excluded_keywords = database_config.EXCLUDED_KEYWORDS[database]
                        self.comparator.set_database_excluded_keywords(database, excluded_keywords)
                        logger.info(f"Set excluded keywords for '{database}': {excluded_keywords}")
                except Exception as e:
                    logger.warning(f"Could not load excluded keywords for database '{database}': {e}")
            
            # Set processing state
            self.set_processing_state(True)
            
            # Initialize progress bar
            total_files = len(json_files_to_process)
            self.progress_bar['maximum'] = total_files
            self.progress_bar['value'] = 0
            
            # Show initial message for very large batches
            if total_files > 50000:
                self.update_progress(0, total_files, f"Starting batch processing of {total_files:,} files... This may take a while.")
                logger.info(f"Starting batch processing of {total_files:,} files")
            else:
                self.update_progress(0, total_files, "Starting comparison...")
            
            # Start processing in background thread
            thread = threading.Thread(
                target=self._process_comparison_batch,
                args=(json_files_to_process,),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            self.set_processing_state(False)
            messagebox.showerror("Error", f"Failed to start comparison: {str(e)}")
            logger.error(f"Comparison start error: {str(e)}", exc_info=True)
            if self.error_log_writer:
                self.error_log_writer.write_error(f"Failed to start comparison: {str(e)}", exc_info=True)
    
    def _process_comparison_batch(self, json_files_to_process: List[str]):
        """Process comparison in background thread with proper batch processing"""
        try:
            # Get field category mapping for the selected database
            database = self.database_var.get()
            field_category_mapping = {}
            if database:
                field_category_mapping = self.field_loader.get_field_category_mapping(database)
            
            total_files = len(json_files_to_process)
            processed = 0
            
            # Determine optimal batch size based on file count
            # For very large datasets (200k+ files), process one at a time to minimize memory
            if total_files > 50000:
                batch_size = 1
                progress_update_interval = 5000  # Update progress every 5000 files (reduced UI updates for better performance)
            elif total_files > 10000:
                batch_size = 1
                progress_update_interval = 100  # Update progress every 100 files
            elif total_files > 1000:
                batch_size = 10
                progress_update_interval = 50  # Update progress every 50 files
            else:
                batch_size = 50
                progress_update_interval = 10  # Update progress every 10 files
            
            # For large datasets, use incremental aggregation
            if total_files > 1000:
                from collections import defaultdict
                field_stats = defaultdict(lambda: {'matched': 0, 'unmatched_db': 0, 'unmatched_json': 0, 'category_null': 0})
                # Track fields that exist in JSON (even if not matched) to avoid false "missing in JSON" reports
                fields_exist_in_json = set()  # Set of field names that exist in at least one JSON file
                # Track array fields and which files are missing them
                array_fields_missing_files = defaultdict(list)  # {field_name: [list of file names where missing]}
                # Identify which fields are array fields (from field_category_mapping)
                array_field_names = set(field_category_mapping.keys()) if field_category_mapping else set()
                file_stats = {'success': 0, 'failed': 0}
                
                # Process files in batches
                for i in range(0, total_files, batch_size):
                    batch = json_files_to_process[i:i + batch_size]
                    
                    for json_file in batch:
                        try:
                            # PERFORMANCE OPTIMIZATION: Load JSON once and reuse for all operations
                            # Load JSON data once (cached for subsequent operations)
                            json_data = self.json_parser.load_json(json_file)
                            if json_data is None:
                                file_stats['failed'] += 1
                                processed += 1
                                continue
                            
                            # Extract fields from already-loaded data (avoid re-reading file)
                            if json_file in self.json_fields:
                                json_fields = self.json_fields[json_file]
                            else:
                                json_fields = sorted(list(set(self.json_parser._extract_all_fields(json_data))))
                                self.json_fields[json_file] = json_fields
                            
                            # Check null categories from already-loaded data
                            null_categories = {}
                            if isinstance(json_data, dict):
                                for key, value in json_data.items():
                                    null_categories[key] = (value is None) or (isinstance(value, list) and len(value) == 0)
                            elif isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
                                for key, value in json_data[0].items():
                                    null_categories[key] = (value is None) or (isinstance(value, list) and len(value) == 0)
                            
                            # Get array field mapping from already-loaded data
                            array_field_mapping = self.json_parser._extract_array_fields_recursive(json_data)
                            
                            # Clean special characters from JSON data if configured for this database
                            if json_data and database:
                                cleaned_data, chars_removed = self.json_parser.clean_special_characters(json_data, database)
                                if chars_removed > 0:
                                    # Save cleaned JSON to cleaned_json folder
                                    cleaned_path = self.json_parser.save_cleaned_json(json_file, cleaned_data)
                                    if cleaned_path:
                                        logger.info(f"Removed {chars_removed} special character(s) from {os.path.basename(json_file)}. Cleaned file saved to: {cleaned_path}")
                                    # Use cleaned data for comparison
                                    json_data = cleaned_data
                            
                            results = self.comparator.compare(
                                self.all_db_fields, 
                                json_fields, 
                                "All Databases", 
                                json_file,
                                field_category_mapping=field_category_mapping,
                                null_categories=null_categories,
                                array_field_mapping=array_field_mapping,
                                json_data=json_data,
                                database_name=database
                            )
                            
                            # Collect validation results
                            validation_results = self.comparator.get_validation_results()
                            self.fields_with_special_chars['db'].extend(validation_results['db'])
                            self.fields_with_special_chars['json'].extend(validation_results['json'])
                            
                            # Write special character validation results to log file in summary format
                            if validation_results['json']:
                                for field_info in validation_results['json']:
                                    special_chars = field_info.get('special_chars', [])
                                    file_name = os.path.basename(json_file)
                                    line_num = field_info.get('line_number')
                                    sample_value = field_info.get('sample_value', '')
                                    if self.special_chars_writer:
                                        self.special_chars_writer.write_json_field(
                                            field_info['field'], special_chars, file_name, line_num, sample_value
                                        )
                            
                            if validation_results['db']:
                                for field_info in validation_results['db']:
                                    special_chars = field_info.get('special_chars', [])
                                    if self.special_chars_writer:
                                        self.special_chars_writer.write_db_field(
                                            field_info['field'], special_chars
                                        )
                            
                            self.comparator.clear_validation_results()
                            
                            # Write field matching results to log file in summary format
                            matched_count = sum(1 for r in results if r.get('status') == 'matched')
                            unmatched_db_count = sum(1 for r in results if r.get('status') == 'unmatched_db' and 'category_null' not in r.get('match_type', ''))
                            unmatched_json_count = sum(1 for r in results if r.get('status') == 'unmatched_json')
                            
                            # Diagnostic: Log if zero matches but fields were extracted
                            if matched_count == 0 and len(json_fields) > 0:
                                logger.warning(f"⚠️ {os.path.basename(json_file)}: {len(json_fields)} fields extracted but 0 matches")
                                logger.warning(f"   Sample JSON fields: {json_fields[:5]}")
                                logger.warning(f"   Sample annexure fields: {self.all_db_fields[:5] if len(self.all_db_fields) > 0 else 'None'}")
                            
                            if self.field_matching_writer:
                                self.field_matching_writer.write_file_result(
                                    os.path.basename(json_file), matched_count, unmatched_db_count, unmatched_json_count
                                )
                            
                            # Collect unmatched fields for log file
                            if unmatched_json_count > 0:
                                for r in results:
                                    if r.get('status') == 'unmatched_json':
                                        if self.field_matching_writer:
                                            self.field_matching_writer.write_unmatched_json_field(
                                                r.get('field_name', ''), r.get('match_type', 'not_found')
                                            )
                            
                            if unmatched_db_count > 0:
                                for r in results:
                                    if r.get('status') == 'unmatched_db' and 'category_null' not in r.get('match_type', ''):
                                        if self.field_matching_writer:
                                            self.field_matching_writer.write_unmatched_db_field(
                                                r.get('field_name', ''), r.get('match_type', 'not_found')
                                            )
                            
                            # Track all fields that exist in this JSON file (matched or unmatched_json)
                            # This helps identify fields that exist in some files but are missing in others
                            for result in results:
                                field_name = result.get('field_name', '')
                                status = result.get('status', '')
                                
                                # If field is matched or unmatched_json, it exists in JSON
                                if status in ['matched', 'unmatched_json']:
                                    fields_exist_in_json.add(field_name)
                            
                            # Aggregate results immediately
                            for result in results:
                                field_name = result.get('field_name', '')
                                status = result.get('status', '')
                                match_type = result.get('match_type', '')
                                
                                if status == 'matched':
                                    field_stats[field_name]['matched'] += 1
                                elif status == 'unmatched_db':
                                    if match_type != 'category_null':
                                        field_stats[field_name]['unmatched_db'] += 1
                                        # Track missing files for array fields
                                        if field_name in array_field_names:
                                            array_fields_missing_files[field_name].append(os.path.basename(json_file))
                                elif status == 'unmatched_json':
                                    field_stats[field_name]['unmatched_json'] += 1
                            
                            # Per-record logging for multi-record files (only log records with unmatched fields)
                            records = self.json_parser.get_records(json_file)
                            if len(records) > 1:
                                records_with_unmatched = []
                                total_unmatched_json = 0
                                total_unmatched_db = 0
                                
                                logger.info(f"File {os.path.basename(json_file)} has {len(records)} records - checking each record for unmatched fields")
                                
                                # Update UI to show multi-record processing
                                self.update_progress(processed, total_files, f"Processing {os.path.basename(json_file)}: {len(records)} records")
                                
                                for record_idx, record in enumerate(records, 1):
                                    # Update UI with current record being processed
                                    if record_idx % 100 == 0 or record_idx == 1 or record_idx == len(records):
                                        self.update_progress(processed, total_files, f"Processing {os.path.basename(json_file)}: Record {record_idx}/{len(records)}")
                                    # Extract fields from this specific record
                                    record_fields = self.json_parser.extract_fields_from_record(record)
                                    
                                    # Check for null categories in this record
                                    record_null_categories = {}
                                    if isinstance(record, dict):
                                        for key, value in record.items():
                                            if value is None:
                                                record_null_categories[key] = True
                                            elif isinstance(value, list) and len(value) == 0:
                                                record_null_categories[key] = True
                                            else:
                                                record_null_categories[key] = False
                                    
                                    # Get array field mapping for this record
                                    # First, get mapping from JSON (fields that actually exist in non-empty arrays)
                                    record_array_mapping = {}
                                    if isinstance(record, dict):
                                        for key, value in record.items():
                                            if isinstance(value, list):
                                                for item in value:
                                                    if isinstance(item, dict):
                                                        for field_name in item.keys():
                                                            normalized_field = field_name.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                                            record_array_mapping[normalized_field] = key
                                    
                                    # Also add database field-to-array mappings for fields that belong to arrays
                                    # This ensures fields from null/empty arrays in JSON can still be matched
                                    # Normalize database field names and map them to their arrays
                                    for db_field, array_name in field_category_mapping.items():
                                        # Normalize the database field name for comparison
                                        normalized_db_field = db_field.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                        # Only add if not already in record_array_mapping (JSON mapping takes precedence)
                                        if normalized_db_field not in record_array_mapping:
                                            # Normalize array name to match JSON array names
                                            normalized_array = array_name.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                            # Check if this array exists in the record (even if null/empty)
                                            if isinstance(record, dict) and any(
                                                key.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower() == normalized_array 
                                                for key in record.keys()
                                            ):
                                                record_array_mapping[normalized_db_field] = array_name
                                    
                                    # Compare this record's fields
                                    record_results = self.comparator.compare(
                                        self.all_db_fields,
                                        record_fields,
                                        "All Databases",
                                        f"{json_file} (Record {record_idx})",
                                        field_category_mapping=field_category_mapping,
                                        null_categories=record_null_categories,
                                        array_field_mapping=record_array_mapping,
                                        json_data=record,
                                        database_name=database
                                    )
                                    
                                    # Find unmatched fields for this record
                                    unmatched_json_fields = [r for r in record_results if r.get('status') == 'unmatched_json']
                                    unmatched_db_fields = [r for r in record_results if r.get('status') == 'unmatched_db']
                                    
                                    if unmatched_json_fields or unmatched_db_fields:
                                        records_with_unmatched.append(record_idx)
                                        total_unmatched_json += len(unmatched_json_fields)
                                        total_unmatched_db += len(unmatched_db_fields)
                                        
                                        # Store per-record unmatched info for summary
                                        if json_file not in self.record_unmatched_info:
                                            self.record_unmatched_info[json_file] = {}
                                        
                                        self.record_unmatched_info[json_file][record_idx] = {
                                            'unmatched_json': [r.get('field_name', '') for r in unmatched_json_fields],
                                            'unmatched_db': [r.get('field_name', '') for r in unmatched_db_fields]
                                        }
                                        
                                        # Log details for this record
                                        logger.warning(f"Record {record_idx}/{len(records)} in {os.path.basename(json_file)} has unmatched fields:")
                                        if unmatched_json_fields:
                                            unmatched_list = [r.get('field_name', '') for r in unmatched_json_fields]
                                            logger.warning(f"  - Fields not found under annexure ({len(unmatched_list)}): {', '.join(unmatched_list[:10])}{'...' if len(unmatched_list) > 10 else ''}")
                                        if unmatched_db_fields:
                                            unmatched_list = [r.get('field_name', '') for r in unmatched_db_fields]
                                            logger.warning(f"  - Missing Annexure fields ({len(unmatched_list)}): {', '.join(unmatched_list[:10])}{'...' if len(unmatched_list) > 10 else ''}")
                                
                                # Update UI with summary
                                if records_with_unmatched:
                                    summary_msg = f"{os.path.basename(json_file)}: {len(records_with_unmatched)}/{len(records)} records have unmatched fields"
                                    self.update_progress(processed, total_files, summary_msg)
                                    logger.warning(f"Summary for {os.path.basename(json_file)}: {len(records_with_unmatched)}/{len(records)} records have unmatched fields (Records: {', '.join(map(str, records_with_unmatched[:20]))}{'...' if len(records_with_unmatched) > 20 else ''})")
                                else:
                                    summary_msg = f"{os.path.basename(json_file)}: All {len(records)} records match correctly"
                                    self.update_progress(processed, total_files, summary_msg)
                                    logger.info(f"All {len(records)} records in {os.path.basename(json_file)} match database fields correctly")
                            
                            file_stats['success'] += 1
                            processed += 1
                            
                            # Update progress for each file (continuous feedback)
                            # For very large datasets, update message less frequently but always update counter
                            if total_files > 50000:
                                # Update counter every file, but message every interval
                                if processed % progress_update_interval == 0 or processed == total_files:
                                    message = f"Processed {processed:,} files"
                                    if file_stats['failed'] > 0:
                                        message += f" - Errors: {file_stats['failed']}"
                                    self.update_progress(processed, total_files, message)
                                else:
                                    # Update counter only (no message change) to show continuous progress
                                    self.update_progress(processed, total_files, "")
                            else:
                                # For smaller datasets, show file name for each file
                                message = f"Processing: {os.path.basename(json_file)}"
                                if file_stats['failed'] > 0:
                                    message += f" - Errors: {file_stats['failed']}"
                                self.update_progress(processed, total_files, message)
                            
                            # Log progress periodically
                            if processed % 1000 == 0:
                                percentage = (processed * 100) // total_files
                                logger.info(f"Processed {processed:,}/{total_files:,} files... ({percentage}%) - Success: {file_stats['success']}, Failed: {file_stats['failed']}")
                                import gc
                                gc.collect()
                            elif processed % 100 == 0 and total_files <= 10000:
                                # More frequent logging for smaller datasets
                                import gc
                                gc.collect()
                        
                        except Exception as e:
                            file_stats['failed'] += 1
                            processed += 1
                            # Only log errors periodically for very large datasets
                            if total_files <= 10000 or processed % 1000 == 0:
                                logger.error(f"Failed to process {json_file}: {str(e)}", exc_info=True)
                                if self.error_log_writer:
                                    self.error_log_writer.write_error(f"Failed to process {json_file}: {str(e)}", exc_info=True, file_path=json_file)
                            # Update progress at intervals - always show error count when there are errors
                            if processed % progress_update_interval == 0:
                                self.update_progress(processed, total_files, f"Errors: {file_stats['failed']}")
                            continue
                    
                    # Clear cache more aggressively for very large datasets
                    if total_files > 50000:
                        # Clear cache every 100 files for 200k+ files
                        if i > 0 and i % 100 == 0:
                            self.json_fields.clear()
                            import gc
                            gc.collect()
                            if i % 10000 == 0:
                                logger.info(f"Cleared cache after processing {processed:,} files")
                    elif i > 0 and i % (batch_size * 10) == 0:
                        self.json_fields.clear()
                        import gc
                        gc.collect()
                        logger.info(f"Cleared cache after processing {processed:,} files")
                
                logger.info(f"Completed processing {processed} JSON files")
                self.update_progress(total_files, total_files, "Aggregating results...")
                
                # Calculate totals for field matching log
                total_matched = sum(s['matched'] for s in field_stats.values())
                total_unmatched_db = sum(s['unmatched_db'] for s in field_stats.values())
                total_unmatched_json = sum(s['unmatched_json'] for s in field_stats.values())
                
                # Write comparison summary to field matching log
                if self.field_matching_writer:
                    self.field_matching_writer.write_comparison_summary(total_matched, total_unmatched_db, total_unmatched_json)
                    self.field_matching_writer.finalize()
                
                # Finalize special characters log
                if self.special_chars_writer:
                    self.special_chars_writer.finalize()
                
                # Close error log
                if self.error_log_writer:
                    self.error_log_writer.close()
                
                # Convert aggregated stats to results format
                # IMPORTANT: If a field exists in JSON in ANY file (matched or unmatched_json),
                # it should NOT be reported as "missing in JSON" (unmatched_db),
                # even if it's missing in other files (e.g., where parent array is null)
                all_results = []
                logger.info(f"Converting {len(field_stats)} field stats to results format")
                for field_name, stats in field_stats.items():
                    if stats['matched'] > 0:
                        # Field exists and matches in at least one file - mark as matched
                        all_results.append({
                            'field_name': field_name,
                            'status': 'matched',
                            'match_type': f"matched ({stats['matched']} times)",
                            'db_field': field_name,
                            'json_field': field_name
                        })
                    elif stats['unmatched_db'] > 0:
                        # For array fields: report if missing in some files (even if exists in others)
                        # For non-array fields: only report if never found in any file
                        if field_name in array_field_names:
                            # Array field: report with file names where it's missing
                            missing_files = array_fields_missing_files.get(field_name, [])
                            if missing_files:
                                # Create a readable list of missing files (limit to first 10 for display)
                                if len(missing_files) <= 10:
                                    files_str = ', '.join(missing_files)
                                else:
                                    files_str = ', '.join(missing_files[:10]) + f" and {len(missing_files) - 10} more"
                                all_results.append({
                                    'field_name': field_name,
                                    'status': 'unmatched_db',
                                    'match_type': f"not_found in: {files_str}",
                                    'db_field': field_name,
                                    'json_field': ''
                                })
                        else:
                            # Non-array field: only report if it does NOT exist in JSON in any file
                            if field_name not in fields_exist_in_json:
                                all_results.append({
                                    'field_name': field_name,
                                    'status': 'unmatched_db',
                                    'match_type': f"not_found ({stats['unmatched_db']} times)",
                                    'db_field': field_name,
                                    'json_field': ''
                                })
                    elif stats['unmatched_json'] > 0:
                        all_results.append({
                            'field_name': field_name,
                            'status': 'unmatched_json',
                            'match_type': f"not_found ({stats['unmatched_json']} times)",
                            'db_field': '',
                            'json_field': field_name
                        })
                
                logger.info(f"Built {len(all_results)} results from {len(field_stats)} field stats")
                logger.info(f"Results breakdown: matched={sum(1 for r in all_results if r.get('status') == 'matched')}, "
                          f"unmatched_db={sum(1 for r in all_results if r.get('status') == 'unmatched_db')}, "
                          f"unmatched_json={sum(1 for r in all_results if r.get('status') == 'unmatched_json')}")
                
                # Schedule UI update on main thread
                self.root.after(0, self._display_results_complete, all_results, file_stats, processed)
                
            else:
                # For smaller batches, collect all results
                all_results = []
                
                for i in range(0, total_files, batch_size):
                    batch = json_files_to_process[i:i + batch_size]
                    
                    for json_file in batch:
                        try:
                            # PERFORMANCE OPTIMIZATION: Load JSON once and reuse for all operations
                            # Load JSON data once (cached for subsequent operations)
                            json_data = self.json_parser.load_json(json_file)
                            if json_data is None:
                                processed += 1
                                continue
                            
                            # Extract fields from already-loaded data (avoid re-reading file)
                            if json_file in self.json_fields:
                                json_fields = self.json_fields[json_file]
                            else:
                                json_fields = sorted(list(set(self.json_parser._extract_all_fields(json_data))))
                                self.json_fields[json_file] = json_fields
                            
                            # Check null categories from already-loaded data
                            null_categories = {}
                            if isinstance(json_data, dict):
                                for key, value in json_data.items():
                                    null_categories[key] = (value is None) or (isinstance(value, list) and len(value) == 0)
                            elif isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
                                for key, value in json_data[0].items():
                                    null_categories[key] = (value is None) or (isinstance(value, list) and len(value) == 0)
                            
                            # Get array field mapping from already-loaded data
                            array_field_mapping = self.json_parser._extract_array_fields_recursive(json_data)
                            
                            # Clean special characters from JSON data if configured for this database
                            if json_data and database:
                                cleaned_data, chars_removed = self.json_parser.clean_special_characters(json_data, database)
                                if chars_removed > 0:
                                    # Save cleaned JSON to cleaned_json folder
                                    cleaned_path = self.json_parser.save_cleaned_json(json_file, cleaned_data)
                                    if cleaned_path:
                                        logger.info(f"Removed {chars_removed} special character(s) from {os.path.basename(json_file)}. Cleaned file saved to: {cleaned_path}")
                                    # Use cleaned data for comparison
                                    json_data = cleaned_data
                            
                            results = self.comparator.compare(
                                self.all_db_fields, 
                                json_fields, 
                                "All Databases", 
                                json_file,
                                field_category_mapping=field_category_mapping,
                                null_categories=null_categories,
                                array_field_mapping=array_field_mapping,
                                json_data=json_data,
                                database_name=database
                            )
                            all_results.extend(results)
                            
                            # Collect validation results
                            validation_results = self.comparator.get_validation_results()
                            self.fields_with_special_chars['db'].extend(validation_results['db'])
                            self.fields_with_special_chars['json'].extend(validation_results['json'])
                            
                            # Write special character validation results to log file in summary format
                            if validation_results['json']:
                                for field_info in validation_results['json']:
                                    special_chars = field_info.get('special_chars', [])
                                    file_name = os.path.basename(json_file)
                                    line_num = field_info.get('line_number')
                                    sample_value = field_info.get('sample_value', '')
                                    if self.special_chars_writer:
                                        self.special_chars_writer.write_json_field(
                                            field_info['field'], special_chars, file_name, line_num, sample_value
                                        )
                            
                            if validation_results['db']:
                                for field_info in validation_results['db']:
                                    special_chars = field_info.get('special_chars', [])
                                    if self.special_chars_writer:
                                        self.special_chars_writer.write_db_field(
                                            field_info['field'], special_chars
                                        )
                            
                            self.comparator.clear_validation_results()
                            
                            # Write field matching results to log file in summary format
                            file_matched = sum(1 for r in results if r.get('status') == 'matched')
                            file_unmatched_db = sum(1 for r in results if r.get('status') == 'unmatched_db' and 'category_null' not in r.get('match_type', ''))
                            file_unmatched_json = sum(1 for r in results if r.get('status') == 'unmatched_json')
                            
                            if self.field_matching_writer:
                                self.field_matching_writer.write_file_result(
                                    os.path.basename(json_file), file_matched, file_unmatched_db, file_unmatched_json
                                )
                            
                            # Collect unmatched fields for log file
                            if file_unmatched_json > 0:
                                for r in results:
                                    if r.get('status') == 'unmatched_json':
                                        if self.field_matching_writer:
                                            self.field_matching_writer.write_unmatched_json_field(
                                                r.get('field_name', ''), r.get('match_type', 'not_found')
                                            )
                            
                            if file_unmatched_db > 0:
                                for r in results:
                                    if r.get('status') == 'unmatched_db' and 'category_null' not in r.get('match_type', ''):
                                        if self.field_matching_writer:
                                            self.field_matching_writer.write_unmatched_db_field(
                                                r.get('field_name', ''), r.get('match_type', 'not_found')
                                            )
                            
                            # Per-record logging for multi-record files (only log records with unmatched fields)
                            records = self.json_parser.get_records(json_file)
                            if len(records) > 1:
                                # Update UI to show multi-record processing
                                self.update_progress(processed, total_files, f"Processing {os.path.basename(json_file)}: {len(records)} records")
                                
                                for record_idx, record in enumerate(records, 1):
                                    # Update UI with current record being processed (every 100 records or at start/end)
                                    if record_idx % 100 == 0 or record_idx == 1 or record_idx == len(records):
                                        self.update_progress(processed, total_files, f"Processing {os.path.basename(json_file)}: Record {record_idx}/{len(records)}")
                                    
                                    # Extract fields from this specific record
                                    record_fields = self.json_parser.extract_fields_from_record(record)
                                    
                                    # Check for null categories in this record
                                    record_null_categories = {}
                                    if isinstance(record, dict):
                                        for key, value in record.items():
                                            if value is None:
                                                record_null_categories[key] = True
                                            elif isinstance(value, list) and len(value) == 0:
                                                record_null_categories[key] = True
                                            else:
                                                record_null_categories[key] = False
                                    
                                    # Get array field mapping for this record
                                    # First, get mapping from JSON (fields that actually exist in non-empty arrays)
                                    record_array_mapping = {}
                                    if isinstance(record, dict):
                                        for key, value in record.items():
                                            if isinstance(value, list):
                                                for item in value:
                                                    if isinstance(item, dict):
                                                        for field_name in item.keys():
                                                            normalized_field = field_name.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                                            record_array_mapping[normalized_field] = key
                                    
                                    # Also add database field-to-array mappings for fields that belong to arrays
                                    # This ensures fields from null/empty arrays in JSON can still be matched
                                    # Normalize database field names and map them to their arrays
                                    for db_field, array_name in field_category_mapping.items():
                                        # Normalize the database field name for comparison
                                        normalized_db_field = db_field.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                        # Only add if not already in record_array_mapping (JSON mapping takes precedence)
                                        if normalized_db_field not in record_array_mapping:
                                            # Normalize array name to match JSON array names
                                            normalized_array = array_name.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower()
                                            # Check if this array exists in the record (even if null/empty)
                                            if isinstance(record, dict) and any(
                                                key.replace(' ', '').replace('_', '').replace('-', '').replace('.', '').lower() == normalized_array 
                                                for key in record.keys()
                                            ):
                                                record_array_mapping[normalized_db_field] = array_name
                                    
                                    # Compare this record's fields
                                    record_results = self.comparator.compare(
                                        self.all_db_fields,
                                        record_fields,
                                        "All Databases",
                                        f"{json_file} (Record {record_idx})",
                                        field_category_mapping=field_category_mapping,
                                        null_categories=record_null_categories,
                                        array_field_mapping=record_array_mapping,
                                        json_data=record,
                                        database_name=database
                                    )
                                    
                                    # Find unmatched fields for this record
                                    unmatched_json_fields = [r for r in record_results if r.get('status') == 'unmatched_json']
                                    unmatched_db_fields = [r for r in record_results if r.get('status') == 'unmatched_db']
                                    
                                    if unmatched_json_fields or unmatched_db_fields:
                                        # Store per-record unmatched info for summary
                                        if json_file not in self.record_unmatched_info:
                                            self.record_unmatched_info[json_file] = {}
                                        
                                        self.record_unmatched_info[json_file][record_idx] = {
                                            'unmatched_json': [r.get('field_name', '') for r in unmatched_json_fields],
                                            'unmatched_db': [r.get('field_name', '') for r in unmatched_db_fields]
                                        }
                            
                            processed += 1
                            
                            # Update progress for each file (continuous feedback)
                            # For very large datasets, update message less frequently but always update counter
                            if total_files > 50000:
                                # Update counter every file, but message every interval
                                if processed % progress_update_interval == 0 or processed == total_files:
                                    self.update_progress(processed, total_files, f"Processed {processed:,} files")
                                else:
                                    # Update counter only (no message change) to show continuous progress
                                    self.update_progress(processed, total_files, "")
                            else:
                                # For smaller datasets, show file name for each file
                                self.update_progress(processed, total_files, f"Processing: {os.path.basename(json_file)}")
                            
                            if processed % 1000 == 0:
                                logger.info(f"Processed {processed:,}/{total_files:,} files...")
                            elif processed % 100 == 0 and total_files <= 10000:
                                logger.info(f"Processed {processed}/{total_files} files...")
                        
                        except Exception as e:
                            if total_files <= 10000 or processed % 1000 == 0:
                                logger.error(f"Failed to process {json_file}: {str(e)}")
                            processed += 1
                            if processed % progress_update_interval == 0:
                                self.update_progress(processed, total_files, f"Processing...")
                            continue
                    
                    # Clear cache periodically (more aggressive for large datasets)
                    if total_files > 50000:
                        if i > 0 and i % 100 == 0:
                            self.json_fields.clear()
                            import gc
                            gc.collect()
                    elif i > 0 and i % (batch_size * 5) == 0:
                        recent_files = list(self.json_fields.keys())[-batch_size:]
                        self.json_fields = {f: self.json_fields[f] for f in recent_files if f in self.json_fields}
                        import gc
                        gc.collect()
                
                logger.info(f"Completed processing {processed} JSON files")
                
                self.update_progress(total_files, total_files, "Processing results...")
                
                # Calculate totals for field matching log
                matched_count = sum(1 for r in all_results if r.get('status') == 'matched')
                unmatched_db_count = sum(1 for r in all_results if r.get('status') == 'unmatched_db' and 'category_null' not in r.get('match_type', ''))
                unmatched_json_count = sum(1 for r in all_results if r.get('status') == 'unmatched_json')
                
                # Write comparison summary to field matching log
                if self.field_matching_writer:
                    self.field_matching_writer.write_comparison_summary(matched_count, unmatched_db_count, unmatched_json_count)
                    self.field_matching_writer.finalize()
                
                # Finalize special characters log
                if self.special_chars_writer:
                    self.special_chars_writer.finalize()
                
                # Close error log
                if self.error_log_writer:
                    self.error_log_writer.close()
                
                # Schedule UI update on main thread
                self.root.after(0, self._display_results_complete, all_results, None, processed)
                
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}", exc_info=True)
            if self.error_log_writer:
                self.error_log_writer.write_error(f"Batch processing error: {str(e)}", exc_info=True)
            self.root.after(0, self._processing_error, str(e))
    
    def _display_results_complete(self, all_results: List[Dict], file_stats: Dict = None, processed: int = 0):
        """Display results on main thread"""
        try:
            # Clear previous results first
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Check if we have any results
            if not all_results or len(all_results) == 0:
                logger.warning(f"No results to display. all_results is empty or None. Processed: {processed} files")
                self.set_processing_state(False)
                self.update_progress(processed, processed, "Comparison complete - No results to display")
                messagebox.showwarning("No Results", 
                                     f"Comparison completed but no results were generated.\n"
                                     f"Processed: {processed} files\n\n"
                                     f"This may indicate:\n"
                                     f"- No fields matched between annexure and JSON files\n"
                                     f"- All JSON files were empty or invalid\n"
                                     f"- Check the log files for details")
                return
            
            # For large batches, use aggregated view
            if len(all_results) > 5000:
                self._display_aggregated_results(all_results)
                if file_stats:
                    messagebox.showinfo("Processing Complete", 
                                       f"Processed {file_stats['success']} files successfully.\n"
                                       f"Failed: {file_stats['failed']}\n"
                                       f"Total: {processed} files")
            else:
                # Display individual results (deduplicate by field name)
                # Use actual file count, not result count
                total_files = len(self.json_files_list) if hasattr(self, 'json_files_list') and self.json_files_list else processed
                self.update_progress(processed, total_files, "Displaying results...")
                matched_count = 0
                unmatched_db_count = 0
                unmatched_json_count = 0
                
                # Track which fields we've already added to avoid duplicates
                seen_fields = set()
                
                logger.info(f"Displaying {len(all_results)} results in GUI")
                
                for result in all_results:
                    status = result['status']
                    match_type = result.get('match_type', 'N/A')
                    field_name = result['field_name']
                    
                    # Create a unique key for this field and status combination
                    # This allows the same field to appear once per status type
                    field_key = (field_name, status)
                    
                    # Skip if we've already added this field with this status
                    if field_key in seen_fields:
                        # Still count it for statistics
                        if status == 'matched':
                            matched_count += 1
                        elif status == 'unmatched_db':
                            unmatched_db_count += 1
                        elif status == 'unmatched_json':
                            unmatched_json_count += 1
                        continue
                    
                    seen_fields.add(field_key)
                    
                    # Display status text for UI
                    display_status = status
                    if status == 'unmatched_json':
                        display_status = 'not found under annexure'
                    elif status == 'unmatched_db':
                        display_status = 'missing in JSON'
                    
                    if status == 'matched':
                        matched_count += 1
                        tag = 'matched'
                    elif status == 'unmatched_db':
                        unmatched_db_count += 1
                        tag = 'unmatched_db'
                    else:
                        unmatched_json_count += 1
                        tag = 'unmatched_json'
                    
                    try:
                        self.results_tree.insert("", tk.END,
                                               text=field_name,
                                               values=(display_status, 
                                                      result.get('db_field', ''),
                                                      result.get('json_field', ''),
                                                      match_type),
                                               tags=(tag,))
                    except Exception as e:
                        logger.error(f"Error inserting result into tree: {str(e)}. Result: {result}")
                        continue
                
                # Verify items were added
                items_added = len(self.results_tree.get_children())
                logger.info(f"Added {items_added} items to results tree. Expected: {len(seen_fields)} unique fields")
                
                if items_added == 0:
                    logger.warning("No items were added to results tree despite having results!")
                    messagebox.showwarning("Display Issue", 
                                         f"Results were generated but could not be displayed.\n"
                                         f"Total results: {len(all_results)}\n"
                                         f"Check log files for details.")
                
                # Configure tags for coloring
                self.results_tree.tag_configure('matched', background='#d4edda')
                self.results_tree.tag_configure('unmatched_db', background='#f8d7da')
                self.results_tree.tag_configure('unmatched_json', background='#fff3cd')
                
                # Update summary
                self.update_summary(matched_count, unmatched_db_count, unmatched_json_count)
                
                # Reset processing state
                self.set_processing_state(False)
                
                # Update progress to show completion
                self.update_progress(processed, total_files, "Comparison complete!")
                
                messagebox.showinfo("Comparison Complete", 
                                  f"Comparison completed!\n"
                                  f"Matched: {matched_count}\n"
                                  f"Missing in JSON: {unmatched_db_count}\n"
                                  f"Not found under annexure: {unmatched_json_count}\n\n"
                                  f"Results displayed: {items_added} fields")
        except Exception as e:
            logger.error(f"Display results error: {str(e)}", exc_info=True)
            if self.error_log_writer:
                self.error_log_writer.write_error(f"Display results error: {str(e)}", exc_info=True)
            self.set_processing_state(False)
            messagebox.showerror("Error", f"Failed to display results: {str(e)}")
    
    def _processing_error(self, error_msg: str):
        """Handle processing error on main thread"""
        self.set_processing_state(False)
        messagebox.showerror("Error", f"Failed to compare fields: {error_msg}")
    
    def _display_aggregated_results(self, all_results: List[Dict]):
        """Display aggregated results for large datasets to save memory"""
        try:
            from collections import defaultdict
            
            logger.info(f"Displaying aggregated results for {len(all_results)} results")
            
            if not all_results or len(all_results) == 0:
                logger.warning("No results to display in aggregated view")
                self.set_processing_state(False)
                messagebox.showwarning("No Results", "No results to display in aggregated view")
                return
            
            # Aggregate results by field name
            field_stats = defaultdict(lambda: {'matched': 0, 'unmatched_db': 0, 'unmatched_json': 0, 'category_null': 0})
            # Track fields that exist in JSON (even if not matched) to avoid false "missing in JSON" reports
            fields_exist_in_json = set()  # Set of field names that exist in at least one JSON file
            # Track array fields and which files are missing them
            array_fields_missing_files = defaultdict(list)  # {field_name: [list of file names where missing]}
            # Get field_category_mapping to identify array fields
            database = self.database_var.get()
            field_category_mapping = {}
            if database:
                field_category_mapping = self.field_loader.get_field_category_mapping(database)
            array_field_names = set(field_category_mapping.keys()) if field_category_mapping else set()
            
            for result in all_results:
                field_name = result.get('field_name', '')
                status = result.get('status', '')
                match_type = result.get('match_type', '')
                json_file = result.get('json_file', '')
                
                # Track fields that exist in JSON (matched or unmatched_json)
                if status in ['matched', 'unmatched_json']:
                    fields_exist_in_json.add(field_name)
                
                if status == 'matched':
                    field_stats[field_name]['matched'] += 1
                elif status == 'unmatched_db':
                    if match_type == 'category_null':
                        field_stats[field_name]['category_null'] += 1
                    else:
                        field_stats[field_name]['unmatched_db'] += 1
                        # Track missing files for array fields
                        if field_name in array_field_names and json_file:
                            file_name = os.path.basename(json_file)
                            if file_name not in array_fields_missing_files[field_name]:
                                array_fields_missing_files[field_name].append(file_name)
                elif status == 'unmatched_json':
                    field_stats[field_name]['unmatched_json'] += 1
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Display aggregated results
            matched_count = 0
            unmatched_db_count = 0
            unmatched_json_count = 0
            category_null_count = 0
            
            for field_name, stats in sorted(field_stats.items()):
                if stats['matched'] > 0:
                    matched_count += stats['matched']
                    tag = 'matched'
                    status = 'matched'
                    match_type = f"matched ({stats['matched']} times)"
                # Skip category_null - don't display as unmatched
                elif stats['unmatched_db'] > 0:
                    # For array fields: report if missing in some files (even if exists in others)
                    # For non-array fields: only report if never found in any file
                    if field_name in array_field_names:
                        # Array field: report with file names where it's missing
                        missing_files = array_fields_missing_files.get(field_name, [])
                        if missing_files:
                            # Create a readable list of missing files (limit to first 10 for display)
                            if len(missing_files) <= 10:
                                files_str = ', '.join(missing_files)
                            else:
                                files_str = ', '.join(missing_files[:10]) + f" and {len(missing_files) - 10} more"
                            unmatched_db_count += stats['unmatched_db']
                            tag = 'unmatched_db'
                            status = 'unmatched_db'
                            match_type = f"not_found in: {files_str}"
                        else:
                            # No missing files tracked (shouldn't happen, but skip to be safe)
                            continue
                    else:
                        # Non-array field: only report if it does NOT exist in JSON in any file
                        if field_name not in fields_exist_in_json:
                            unmatched_db_count += stats['unmatched_db']
                            tag = 'unmatched_db'
                            status = 'unmatched_db'
                            match_type = f"not_found ({stats['unmatched_db']} times)"
                        else:
                            # Field exists in JSON in some files, skip unmatched_db report
                            continue
                elif stats['unmatched_json'] > 0:
                    unmatched_json_count += stats['unmatched_json']
                    tag = 'unmatched_json'
                    status = 'unmatched_json'
                    display_status = 'not found under annexure'
                    match_type = f"not_found ({stats['unmatched_json']} times)"
                else:
                    # Skip fields that only have category_null
                    continue
                
                # Set display_status for unmatched_db as well
                if status == 'unmatched_db':
                    display_status = 'missing in JSON'
                elif status == 'matched':
                    display_status = 'matched'
                
                try:
                    self.results_tree.insert("", tk.END,
                                           text=field_name,
                                           values=(display_status, '', '', match_type),
                                           tags=(tag,))
                except Exception as e:
                    logger.error(f"Error inserting aggregated result into tree: {str(e)}. Field: {field_name}")
                    continue
            
            # Verify items were added
            items_added = len(self.results_tree.get_children())
            logger.info(f"Added {items_added} items to results tree in aggregated view")
            
            if items_added == 0:
                logger.warning("No items were added to results tree in aggregated view!")
                self.set_processing_state(False)
                messagebox.showwarning("Display Issue", 
                                     f"Results were generated but could not be displayed.\n"
                                     f"Total results: {len(all_results)}\n"
                                     f"Field stats: {len(field_stats)}\n"
                                     f"Check log files for details.")
                return
            
            # Configure tags for coloring
            self.results_tree.tag_configure('matched', background='#d4edda')
            self.results_tree.tag_configure('unmatched_db', background='#f8d7da')
            self.results_tree.tag_configure('category_null', background='#ffcccc')
            self.results_tree.tag_configure('unmatched_json', background='#fff3cd')
            
            # Update summary (category_null excluded from unmatched count)
            self.update_summary(matched_count, unmatched_db_count, unmatched_json_count)
            
            # Reset processing state
            self.set_processing_state(False)
            
            messagebox.showinfo("Aggregated Results", 
                               f"Aggregated results displayed!\n\n"
                               f"Unique Fields: {len(field_stats)}\n"
                               f"Items Displayed: {items_added}\n"
                               f"Total Matches: {matched_count}\n"
                               f"Missing in JSON: {unmatched_db_count}\n"
                               f"Not found under annexure: {unmatched_json_count}\n\n"
                               f"Note: Fields with null/empty arrays are excluded from unmatched count.")
        except Exception as e:
            logger.error(f"Error displaying aggregated results: {str(e)}", exc_info=True)
            self.set_processing_state(False)
            messagebox.showerror("Error", f"Failed to display aggregated results: {str(e)}")
    
    def update_summary(self, matched, unmatched_db, unmatched_json):
        """Update summary tab - simple summary only, detailed logs are in log files"""
        self.summary_text.delete(1.0, tk.END)
        
        # Count unique unmatched fields without loading all details
        total_unmatched_db_count = unmatched_db
        total_unmatched_json_count = unmatched_json
        
        # Count special character fields (just count, don't process details)
        special_chars_db_count = len(set(f.get('field', '') for f in self.fields_with_special_chars['db'])) if self.fields_with_special_chars['db'] else 0
        special_chars_json_count = len(set(f.get('field', '') for f in self.fields_with_special_chars['json'])) if self.fields_with_special_chars['json'] else 0
        
        # Count multi-record files with issues (just count, don't process details)
        multi_record_files_count = 0
        total_records_with_issues = 0
        for json_file in self.json_fields.keys():
            records = self.json_parser.get_records(json_file)
            if len(records) > 1:
                multi_record_files_count += 1
                record_info = self.record_unmatched_info.get(json_file, {})
                total_records_with_issues += len(record_info)
        
        summary = f"""
FIELD COMPARISON SUMMARY
{'='*60}

ANNEXURE FIELDS:
{'-'*60}
Total Annexure Fields: {len(self.all_db_fields)}
Total Annexures: {len(self.field_loader.get_databases()) if self.loader_data else 0}

JSON FILES:
{'-'*60}
Total JSON Files Processed: {len(self.json_fields):,}

COMPARISON RESULTS:
{'-'*60}
Matched Fields: {matched:,}
Missing in JSON: {unmatched_db:,}
Not found under annexure: {unmatched_json:,}
Total Compared: {matched + unmatched_db + unmatched_json:,}

UNMATCHED FIELDS SUMMARY:
{'-'*60}
Missing in JSON Fields: {total_unmatched_db_count:,}
Fields not found under annexure: {total_unmatched_json_count:,}

MULTI-RECORD FILES:
{'-'*60}
Multi-record files processed: {multi_record_files_count:,}
Total records with unmatched fields: {total_records_with_issues:,}

SPECIAL CHARACTER VALIDATION:
{'-'*60}
Annexure fields with special characters: {special_chars_db_count:,}
JSON fields with special characters: {special_chars_json_count:,}

{'='*60}
NOTE: Detailed logs with full field names, file details, per-record analysis,
and special character information are available in the log files.
Check the 'logs' folder for complete information.
{'='*60}
"""
        
        self.summary_text.insert(1.0, summary)
        
        # ============================================================================
        # OLD DETAILED CODE - COMMENTED OUT FOR PERFORMANCE (causes crashes with large datasets)
        # All detailed information is still logged to log files
        # ============================================================================
        
        # # OLD CODE: Show all annexure fields with list
        # summary += f"\n\nANNEXURE FIELDS (All Annexures Combined):\n{'-'*50}\n"
        # summary += f"Total Fields: {len(self.all_db_fields)}\n"
        # summary += f"Total Annexures: {len(self.field_loader.get_databases()) if self.loader_data else 0}\n"
        # summary += f"Fields from all annexures/tables:\n"
        # summary += f"{', '.join(self.all_db_fields[:50])}\n"
        # if len(self.all_db_fields) > 50:
        #     summary += f"... and {len(self.all_db_fields) - 50} more fields\n"
        
        # # OLD CODE: Iterate through all JSON files to show details (SLOW for large datasets)
        # summary += f"\n\nJSON FIELDS:\n{'-'*50}\n"
        # for json_file, fields in self.json_fields.items():
        #     summary += f"\nFile: {os.path.basename(json_file)}\n"
        #     summary += f"Total Fields: {len(fields)}\n"
        #     summary += f"Fields: {', '.join(fields)}\n"
        
        # # OLD CODE: Get unmatched fields details (VERY SLOW - iterates through millions of tree items)
        # unmatched_fields = self.get_unmatched_fields()
        # if unmatched_fields['unmatched_db'] or unmatched_fields['unmatched_json'] or unmatched_fields['category_null']:
        #     summary += f"\n\nUNMATCHED FIELDS DETAILS:\n{'-'*50}\n"
        #     
        #     if unmatched_fields['unmatched_db']:
        #         summary += f"\nMissing in JSON Fields ({len(unmatched_fields['unmatched_db'])}):\n"
        #         for field_info in unmatched_fields['unmatched_db']:
        #             summary += f"  - {field_info['field_name']}: {field_info['match_type']}\n"
        #     
        #     if unmatched_fields['category_null']:
        #         summary += f"\nFields with Null Categories ({len(unmatched_fields['category_null'])}):\n"
        #         for field_info in unmatched_fields['category_null']:
        #             summary += f"  - {field_info['field_name']}: {field_info['match_type']}\n"
        #     
        #     if unmatched_fields['unmatched_json']:
        #         summary += f"\nFields not found under annexure ({len(unmatched_fields['unmatched_json'])}):\n"
        #         for field_info in unmatched_fields['unmatched_json']:
        #             summary += f"  - {field_info['field_name']}: {field_info['match_type']}\n"
        
        # # OLD CODE: Per-record details for multi-record files (VERY SLOW for large datasets)
        # has_multi_record_files = False
        # for json_file in self.json_fields.keys():
        #     records = self.json_parser.get_records(json_file)
        #     if len(records) > 1:
        #         has_multi_record_files = True
        #         break
        # 
        # if has_multi_record_files:
        #     summary += f"\n\nPER-RECORD ANALYSIS (Multi-Record Files):\n{'-'*50}\n"
        #     
        #     for json_file, fields in self.json_fields.items():
        #         records = self.json_parser.get_records(json_file)
        #         if len(records) > 1:
        #             total_records = len(records)
        #             record_info = self.record_unmatched_info.get(json_file, {})
        #             records_with_issues = len(record_info)
        #             
        #             summary += f"\nFile: {os.path.basename(json_file)}\n"
        #             summary += f"Total Records: {total_records}\n"
        #             summary += f"Records with Unmatched Fields: {records_with_issues}\n"
        #             
        #             if records_with_issues > 0:
        #                 summary += f"\nRecords with Issues:\n"
        #                 all_record_numbers = sorted(list(record_info.keys()))
        #                 for record_idx in all_record_numbers:
        #                     info = record_info[record_idx]
        #                     summary += f"  Record {record_idx}:\n"
        #                     if info.get('unmatched_json'):
        #                         unmatched_list = info['unmatched_json']
        #                         summary += f"    - Fields not found under annexure ({len(unmatched_list)}): {', '.join(unmatched_list[:5])}{'...' if len(unmatched_list) > 5 else ''}\n"
        #                     if info.get('unmatched_db'):
        #                         unmatched_list = info['unmatched_db']
        #                         summary += f"    - Missing Annexure fields ({len(unmatched_list)}): {', '.join(unmatched_list[:5])}{'...' if len(unmatched_list) > 5 else ''}\n"
        #             else:
        #                 summary += f"  ✓ All {total_records} records match annexure fields correctly\n"
        
        # # OLD CODE: Special character validation results (SLOW for large datasets)
        # summary += f"\n\nSPECIAL CHARACTER VALIDATION:\n{'-'*50}\n"
        # summary += f"Fields with special characters in VALUES (excluding HELM, MolStructure, SMILES fields):\n\n"
        # 
        # if not self.fields_with_special_chars['db'] and not self.fields_with_special_chars['json']:
        #     summary += f"No special characters found in field values.\n\n"
        # else:
        #     if self.fields_with_special_chars['db']:
        #         field_to_chars = {}
        #         for f in self.fields_with_special_chars['db']:
        #             field_name = f['field']
        #             special_chars = f.get('special_chars', [])
        #             if field_name not in field_to_chars:
        #                 field_to_chars[field_name] = set()
        #             field_to_chars[field_name].update(special_chars)
        #         
        #         unique_db_fields = sorted(field_to_chars.keys())
        #         summary += f"Annexure Fields ({len(unique_db_fields)}):\n"
        #         for field in unique_db_fields:
        #             chars_list = sorted(list(field_to_chars[field]))
        #             chars_str = ', '.join([f"'{c}'" for c in chars_list])
        #             summary += f"  - {field}: special characters [{chars_str}]\n"
        #     
        #     if self.fields_with_special_chars['json']:
        #         field_to_info = {}
        #         for f in self.fields_with_special_chars['json']:
        #             field_name = f['field']
        #             special_chars = f.get('special_chars', [])
        #             
        #             if not special_chars or len(special_chars) == 0:
        #                 continue
        #             
        #             sample_value = f.get('sample_value', '')
        #             file_path = f.get('file', '')
        #             line_number = f.get('line_number')
        #             
        #             if field_name not in field_to_info:
        #                 field_to_info[field_name] = {
        #                     'special_chars': set(),
        #                     'sample_value': sample_value,
        #                     'files': []
        #                 }
        #             field_to_info[field_name]['special_chars'].update(special_chars)
        #             if not field_to_info[field_name]['sample_value']:
        #                 field_to_info[field_name]['sample_value'] = sample_value
        #             if file_path:
        #                 file_name = os.path.basename(file_path)
        #                 field_to_info[field_name]['files'].append((file_name, line_number))
        #         
        #         unique_json_fields = sorted(field_to_info.keys())
        #         summary += f"\nJSON Fields ({len(unique_json_fields)}):\n"
        #         for field in unique_json_fields:
        #             info = field_to_info[field]
        #             chars_list = sorted(list(info['special_chars']))
        #             chars_str = ', '.join([f"'{c}'" for c in chars_list])
        #             sample = info['sample_value']
        #             
        #             file_info_parts = []
        #             for file_name, line_num in info['files']:
        #                 if line_num:
        #                     file_info_parts.append(f"{file_name}:{line_num}")
        #                 else:
        #                     file_info_parts.append(file_name)
        #             file_info = ", ".join(file_info_parts) if file_info_parts else ""
        #             
        #             if sample:
        #                 sample_display = sample[:80] + '...' if len(sample) > 80 else sample
        #                 if file_info:
        #                     summary += f"  - {field}: special characters [{chars_str}], file: {file_info}, sample value: \"{sample_display}\"\n"
        #                 else:
        #                     summary += f"  - {field}: special characters [{chars_str}], sample value: \"{sample_display}\"\n"
        #             else:
        #                 if file_info:
        #                     summary += f"  - {field}: special characters [{chars_str}], file: {file_info}\n"
        #                 else:
        #                     summary += f"  - {field}: special characters [{chars_str}]\n"
    
    def show_unmatched_fields(self):
        """Display unmatched fields in a message box"""
        unmatched_fields = self.get_unmatched_fields()
        
        if not unmatched_fields['unmatched_db'] and not unmatched_fields['unmatched_json'] and not unmatched_fields['category_null']:
            messagebox.showinfo("Unmatched Fields", "No unmatched fields found. All fields are matched!")
            return
        
        message = "UNMATCHED FIELDS REPORT\n" + "="*60 + "\n\n"
        
        if unmatched_fields['unmatched_db']:
            message += f"MISSING IN JSON FIELDS ({len(unmatched_fields['unmatched_db'])}):\n"
            message += "-"*60 + "\n"
            for field_info in unmatched_fields['unmatched_db']:
                message += f"  • {field_info['field_name']}\n"
                message += f"    Status: {field_info['match_type']}\n\n"
        
        if unmatched_fields['category_null']:
            message += f"FIELDS WITH NULL CATEGORIES ({len(unmatched_fields['category_null'])}):\n"
            message += "-"*60 + "\n"
            for field_info in unmatched_fields['category_null']:
                message += f"  • {field_info['field_name']}\n"
                message += f"    Status: {field_info['match_type']}\n\n"
        
        if unmatched_fields['unmatched_json']:
            message += f"FIELDS NOT FOUND UNDER ANNEXURE ({len(unmatched_fields['unmatched_json'])}):\n"
            message += "-"*60 + "\n"
            for field_info in unmatched_fields['unmatched_json']:
                message += f"  • {field_info['field_name']}\n"
                message += f"    Status: {field_info['match_type']}\n\n"
        
        # Create a scrolled text window for large lists
        if len(message) > 2000:
            # Create a new window for displaying large results
            window = tk.Toplevel(self.root)
            window.title("Unmatched Fields Report")
            window.geometry("700x500")
            
            text_widget = scrolledtext.ScrolledText(window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True)
            # Optimize text insertion for large messages
            text_widget.config(state=tk.NORMAL)
            if len(message) > 100000:
                chunk_size = 50000
                chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]
                text_widget.insert(1.0, chunks[0])
                for chunk in chunks[1:]:
                    text_widget.insert(tk.END, chunk)
                    text_widget.update_idletasks()
            else:
                text_widget.insert(1.0, message)
            text_widget.config(state=tk.DISABLED)
            
            ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)
        else:
            messagebox.showinfo("Unmatched Fields", message)
    
    def show_evolvus_id_unmatched(self):
        """Display unmatched fields specifically for evolvus_id (excluding null array fields)"""
        unmatched_fields = self.get_unmatched_fields_for_evolvus_id()
        
        if not unmatched_fields['unmatched_db'] and not unmatched_fields['unmatched_json']:
            messagebox.showinfo("Evolvus ID Unmatched Fields", 
                              "No unmatched fields found for evolvus_id.\n\n"
                              "Note: Fields with null/empty arrays are excluded from unmatched list.")
            return
        
        message = "UNMATCHED FIELDS FOR EVOLVUS_ID\n"
        message += "="*70 + "\n\n"
        message += "Note: Fields with null/empty arrays are excluded.\n\n"
        
        if unmatched_fields['unmatched_db']:
            message += f"MISSING IN JSON FIELDS ({len(unmatched_fields['unmatched_db'])}):\n"
            message += "-"*70 + "\n"
            for field_info in unmatched_fields['unmatched_db']:
                message += f"  • {field_info['field_name']}\n"
                message += f"    Status: {field_info['match_type']}\n"
                if field_info.get('category'):
                    message += f"    Category: {field_info['category']}\n"
                message += "\n"
        
        if unmatched_fields['unmatched_json']:
            message += f"FIELDS NOT FOUND UNDER ANNEXURE ({len(unmatched_fields['unmatched_json'])}):\n"
            message += "-"*70 + "\n"
            for field_info in unmatched_fields['unmatched_json']:
                message += f"  • {field_info['field_name']}\n"
                message += f"    Status: {field_info['match_type']}\n"
                if field_info.get('category'):
                    message += f"    Category: {field_info['category']}\n"
                message += "\n"
        
        # Create a window for displaying results
        window = tk.Toplevel(self.root)
        window.title("Evolvus ID - Unmatched Fields")
        window.geometry("700x500")
        
        text_widget = scrolledtext.ScrolledText(window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        # Optimize text insertion for large messages
        text_widget.config(state=tk.NORMAL)
        if len(message) > 100000:
            chunk_size = 50000
            chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]
            text_widget.insert(1.0, chunks[0])
            for chunk in chunks[1:]:
                text_widget.insert(tk.END, chunk)
                text_widget.update_idletasks()
        else:
            text_widget.insert(1.0, message)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)
    
    def show_special_characters(self):
        """Display special characters in a separate window with file names and line numbers"""
        if not self.fields_with_special_chars['db'] and not self.fields_with_special_chars['json']:
            messagebox.showinfo("No Special Characters", "No special characters found in field values.")
            return
        
        # Create a new window for displaying special characters
        window = tk.Toplevel(self.root)
        window.title("Special Characters Validation Report")
        window.geometry("900x600")
        
        # Create a scrolled text widget
        text_widget = scrolledtext.ScrolledText(window, wrap=tk.WORD, padx=10, pady=10, font=("Courier", 9))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Disable widget updates during insertion for better performance
        text_widget.config(state=tk.NORMAL)
        
        message = "SPECIAL CHARACTER VALIDATION REPORT\n"
        message += "=" * 80 + "\n\n"
        message += "Fields with special characters in VALUES (excluding HELM, MolStructure, SMILES fields):\n\n"
        
        if self.fields_with_special_chars['db']:
            message += "ANNEXURE FIELDS:\n"
            message += "-" * 80 + "\n"
            field_to_chars = {}
            for f in self.fields_with_special_chars['db']:
                field_name = f['field']
                special_chars = f.get('special_chars', [])
                if field_name not in field_to_chars:
                    field_to_chars[field_name] = set()
                field_to_chars[field_name].update(special_chars)
            
            for field in sorted(field_to_chars.keys()):
                chars_list = sorted(list(field_to_chars[field]))
                chars_str = ', '.join([f"'{c}'" for c in chars_list])
                message += f"  • {field}: special characters [{chars_str}]\n"
            message += "\n"
        
        if self.fields_with_special_chars['json']:
            message += "JSON FIELDS:\n"
            message += "-" * 80 + "\n"
            
            # Group by field but keep all file/line info
            # Only include entries that actually have special characters
            field_to_info = {}
            for f in self.fields_with_special_chars['json']:
                field_name = f['field']
                special_chars = f.get('special_chars', [])
                
                # Skip if no special characters found (shouldn't happen, but double-check)
                if not special_chars or len(special_chars) == 0:
                    continue
                
                sample_value = f.get('sample_value', '')
                file_path = f.get('file', '')
                line_number = f.get('line_number')
                
                if field_name not in field_to_info:
                    field_to_info[field_name] = {
                        'special_chars': set(),
                        'occurrences': []  # List of (file, line_number, sample_value, special_chars) tuples
                    }
                field_to_info[field_name]['special_chars'].update(special_chars)
                if file_path:
                    file_name = os.path.basename(file_path)
                    # Store the special chars for this specific occurrence
                    field_to_info[field_name]['occurrences'].append((file_name, line_number, sample_value, special_chars))
            
            for field in sorted(field_to_info.keys()):
                info = field_to_info[field]
                chars_list = sorted(list(info['special_chars']))
                chars_str = ', '.join([f"'{c}'" for c in chars_list])
                message += f"\n  • {field}:\n"
                message += f"      Special characters: [{chars_str}]\n"
                
                # Show occurrences with file names and line numbers
                # Limit to first 50 occurrences per field to prevent UI freezing
                occurrences_to_show = info['occurrences'][:50]
                total_occurrences = len(info['occurrences'])
                
                for file_name, line_num, sample, occ_chars in occurrences_to_show:
                    # Double-check this occurrence has special characters
                    if not occ_chars or len(occ_chars) == 0:
                        continue
                    
                    occ_chars_str = ', '.join([f"'{c}'" for c in sorted(occ_chars)])
                    if line_num:
                        message += f"      - File: {file_name}, Line: {line_num}\n"
                    else:
                        message += f"      - File: {file_name}\n"
                    message += f"        Special characters in this occurrence: [{occ_chars_str}]\n"
                    if sample:
                        sample_display = sample[:100] + '...' if len(sample) > 100 else sample
                        message += f"        Sample value: \"{sample_display}\"\n"
                
                # Show truncation message if there are more occurrences
                if total_occurrences > 50:
                    message += f"      ... ({total_occurrences - 50} more occurrence(s) not shown)\n"
        
        text_widget.insert(1.0, message)
        text_widget.config(state=tk.DISABLED)
        
        # Add close button
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)
    
    def export_results(self):
        """Export comparison results to file"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Export Results",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if filename:
                results = {
                    'database_fields': self.db_fields,
                    'all_database_fields': self.all_db_fields,
                    'total_database_fields': len(self.all_db_fields),
                    'json_fields': self.json_fields,
                    'comparison_summary': self.get_comparison_summary()
                }
                
                with open(filename, 'w') as f:
                    json.dump(results, f, indent=2)
                
                messagebox.showinfo("Success", f"Results exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export results: {str(e)}")
    
    def export_unmatched_json_fields(self):
        """Export unmatched JSON fields to a separate file"""
        try:
            unmatched_fields = self.get_unmatched_fields()
            unmatched_json_fields = unmatched_fields.get('unmatched_json', [])
            
            if not unmatched_json_fields:
                messagebox.showinfo("No Fields Found", "No fields not found under annexure to export.")
                return
            
            filename = filedialog.asksaveasfilename(
                title="Export Fields Not Found Under Annexure",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if filename:
                # Collect all unique unmatched JSON field names
                unique_fields = list(set([field['field_name'] for field in unmatched_json_fields]))
                unique_fields.sort()
                
                # Also collect from per-record unmatched info
                for json_file, record_info in self.record_unmatched_info.items():
                    for record_idx, info in record_info.items():
                        if info.get('unmatched_json'):
                            for field_name in info['unmatched_json']:
                                if field_name not in unique_fields:
                                    unique_fields.append(field_name)
                
                unique_fields.sort()
                
                # Prepare export data
                export_data = {
                    'total_unmatched_json_fields': len(unique_fields),
                    'unmatched_fields': unique_fields,
                    'detailed_info': unmatched_json_fields,
                    'export_timestamp': str(datetime.now()),
                    'files_analyzed': [os.path.basename(f) for f in self.json_fields.keys()]
                }
                
                # Write to file
                if filename.endswith('.txt'):
                    # Text format
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("FIELDS NOT FOUND UNDER ANNEXURE\n")
                        f.write("=" * 50 + "\n\n")
                        f.write(f"Total Fields Not Found: {len(unique_fields)}\n")
                        f.write(f"Export Date: {export_data['export_timestamp']}\n\n")
                        f.write("Fields (in JSON but not found under annexure):\n")
                        f.write("-" * 50 + "\n")
                        for field in unique_fields:
                            f.write(f"  - {field}\n")
                        f.write("\n\nDetailed Information:\n")
                        f.write("-" * 50 + "\n")
                        for field_info in unmatched_json_fields:
                            f.write(f"  - {field_info['field_name']}: {field_info.get('match_type', 'not_found')}\n")
                else:
                    # JSON format
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Success", 
                    f"Fields not found under annexure exported to:\n{filename}\n\n"
                    f"Total fields: {len(unique_fields)}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export fields not found under annexure: {str(e)}")
    
    def get_comparison_summary(self):
        """Get comparison summary data"""
        summary = {
            'matched': 0,
            'unmatched_db': 0,
            'unmatched_json': 0
        }
        
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item, 'values')
            status = values[0]
            if status == 'matched':
                summary['matched'] += 1
            elif status == 'unmatched_db':
                summary['unmatched_db'] += 1
            else:
                summary['unmatched_json'] += 1
        
        return summary
    
    def get_unmatched_fields(self):
        """Get list of all unmatched fields categorized by type (excluding null array fields)"""
        # Use dictionaries to track unique fields (deduplicate by field_name)
        unmatched_db_dict = {}      # {field_name: match_type}
        unmatched_json_dict = {}    # {field_name: match_type}
        category_null_dict = {}     # {field_name: match_type}
        
        for item in self.results_tree.get_children():
            field_name = self.results_tree.item(item, 'text')
            values = self.results_tree.item(item, 'values')
            display_status = values[0]
            match_type = values[3] if len(values) > 3 else ''
            
            # Convert display status back to internal status
            if display_status == 'not found under annexure':
                status = 'unmatched_json'
            elif display_status == 'missing in JSON':
                status = 'unmatched_db'
            else:
                status = display_status
            
            if status == 'unmatched_db':
                if 'category_null' in match_type:
                    # Store for reference but don't count as unmatched
                    if field_name not in category_null_dict:
                        category_null_dict[field_name] = match_type
                else:
                    # Only store once per field name (deduplicate)
                    if field_name not in unmatched_db_dict:
                        unmatched_db_dict[field_name] = match_type
            elif status == 'unmatched_json':
                # Only store once per field name (deduplicate)
                if field_name not in unmatched_json_dict:
                    unmatched_json_dict[field_name] = match_type
        
        # Convert dictionaries to lists
        unmatched_fields = {
            'unmatched_db': [{'field_name': name, 'match_type': match_type} 
                            for name, match_type in unmatched_db_dict.items()],
            'unmatched_json': [{'field_name': name, 'match_type': match_type} 
                              for name, match_type in unmatched_json_dict.items()],
            'category_null': [{'field_name': name, 'match_type': match_type} 
                             for name, match_type in category_null_dict.items()]
        }
        
        return unmatched_fields
    
    def get_unmatched_fields_for_evolvus_id(self):
        """Get list of unmatched fields specifically for evolvus_id (excluding null array fields)"""
        unmatched_fields = {
            'unmatched_db': [],
            'unmatched_json': []
        }
        
        # Get field category mapping to identify fields under evolvus_id
        database = self.database_var.get()
        field_category_mapping = {}
        if database:
            field_category_mapping = self.field_loader.get_field_category_mapping(database)
        
        # Normalize evolvus_id for comparison
        evolvus_id_normalized = 'evolvusid'.replace(' ', '').replace('_', '').replace('-', '').lower()
        
        for item in self.results_tree.get_children():
            field_name = self.results_tree.item(item, 'text')
            values = self.results_tree.item(item, 'values')
            status = values[0]
            match_type = values[3] if len(values) > 3 else ''
            
            # Skip fields with null categories
            if 'category_null' in match_type:
                continue
            
            # Check if field belongs to evolvus_id category
            category = field_category_mapping.get(field_name, '')
            if category:
                normalized_cat = category.replace(' ', '').replace('_', '').replace('-', '').lower()
                if normalized_cat == evolvus_id_normalized:
                    if status == 'unmatched_db':
                        unmatched_fields['unmatched_db'].append({
                            'field_name': field_name,
                            'match_type': match_type,
                            'category': category
                        })
                    elif status == 'unmatched_json':
                        unmatched_fields['unmatched_json'].append({
                            'field_name': field_name,
                            'match_type': match_type,
                            'category': category
                        })
            # Also check if field name itself contains evolvus_id pattern
            elif 'evolvus' in field_name.lower():
                if status == 'unmatched_db':
                    unmatched_fields['unmatched_db'].append({
                        'field_name': field_name,
                        'match_type': match_type,
                        'category': 'evolvus_id'
                    })
                elif status == 'unmatched_json':
                    unmatched_fields['unmatched_json'].append({
                        'field_name': field_name,
                        'match_type': match_type,
                        'category': 'evolvus_id'
                    })
        
        return unmatched_fields
    
    def clear_all(self):
        """Clear all data and results (but keep database fields loaded)"""
        self.json_fields = {}
        self.comparison_results = {}
        self.json_folder = None
        self.json_files_list = []
        self.json_folder_var.set("")  # Clear folder display
        self.record_unmatched_info = {}  # Clear per-record unmatched info
        self.fields_with_special_chars = {'db': [], 'json': []}  # Clear special character validation results
        
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.summary_text.delete(1.0, tk.END)
        
        # Clear processing status
        self.progress_status_var.set("Ready")
        self.progress_bar['value'] = 0
        self.progress_bar.grid_remove()  # Hide progress bar
        self.is_processing = False
        
        messagebox.showinfo("Cleared", "JSON fields and comparison results cleared.\nAnnexure fields remain loaded.")
    
    def _open_log_file(self, log_file_path: str, log_type: str = "log"):
        """Helper method to open a log file in the default text editor"""
        try:
            if not log_file_path:
                messagebox.showerror("Error", f"{log_type} file path not found.")
                return
            
            if not os.path.exists(log_file_path):
                messagebox.showerror("Error", f"{log_type} file not found:\n{log_file_path}")
                return
            
            # Open the log file with the default system application
            system = platform.system()
            try:
                if system == 'Windows':
                    os.startfile(log_file_path)
                elif system == 'Darwin':  # macOS
                    subprocess.run(['open', log_file_path])
                else:  # Linux and other Unix-like systems
                    subprocess.run(['xdg-open', log_file_path])
                
                logger.info(f"Opened {log_type} file: {log_file_path}")
            except Exception as e:
                # Fallback: try to open with notepad on Windows or default editor
                try:
                    if system == 'Windows':
                        subprocess.run(['notepad', log_file_path])
                    else:
                        # Try common text editors
                        editors = ['gedit', 'nano', 'vi', 'vim', 'code', 'subl']
                        for editor in editors:
                            try:
                                subprocess.run([editor, log_file_path])
                                break
                            except FileNotFoundError:
                                continue
                        else:
                            raise Exception("No suitable text editor found")
                except Exception as fallback_error:
                    messagebox.showerror("Error", 
                                       f"Failed to open {log_type} file:\n{str(e)}\n\n"
                                       f"Please manually open:\n{log_file_path}")
                    logger.error(f"Failed to open {log_type} file: {str(e)}", exc_info=True)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {log_type} file: {str(e)}")
            logger.error(f"Log viewer error: {str(e)}", exc_info=True)
    
    def show_log_menu(self):
        """Show a menu to select which log file to open"""
        if not self.current_log_files:
            messagebox.showinfo("No Log Files", "No log files available. Please run a comparison first.")
            return
        
        # Create a popup menu
        menu = tk.Menu(self.root, tearoff=0)
        
        # Add option to open logs folder
        menu.add_command(label="Open Logs Folder", command=self.view_log_files)
        menu.add_separator()
        
        # Build list of available log files
        log_options = []
        
        # Special Characters Log (only final, available after processing)
        if not self.is_processing:
            final_path = self.current_log_files.get('special_chars')
            if final_path and os.path.exists(final_path):
                log_options.append(("Special Characters", final_path, "Special characters logs"))
        
        # Field Matching Log (only final, available after processing)
        if not self.is_processing:
            final_path = self.current_log_files.get('field_matching')
            if final_path and os.path.exists(final_path):
                log_options.append(("Field Matching", final_path, "Field matching logs"))
        
        # Error Log (always available if it exists)
        error_path = self.current_log_files.get('errors')
        if error_path and os.path.exists(error_path):
            log_options.append(("Error Log", error_path, "Error log"))
        
        # Add log file options to menu
        if log_options:
            for label, file_path, log_type in log_options:
                menu.add_command(label=label, command=lambda p=file_path, t=log_type: self._open_log_file(p, t))
        else:
            menu.add_command(label="No log files available yet", state=tk.DISABLED)
        
        # Show menu at button location
        try:
            # Get button position
            button_x = self.view_logs_button.winfo_rootx()
            button_y = self.view_logs_button.winfo_rooty() + self.view_logs_button.winfo_height()
            menu.post(button_x, button_y)
        except Exception as e:
            # Fallback: show menu at cursor position
            menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())
    
    def view_log_files(self):
        """Open the logs folder in file explorer"""
        try:
            logs_dir = os.path.abspath(self.logs_dir)
            
            if not os.path.exists(logs_dir):
                messagebox.showerror("Error", f"Logs directory not found:\n{logs_dir}")
                return
            
            # Open the logs directory in file explorer
            system = platform.system()
            try:
                if system == 'Windows':
                    os.startfile(logs_dir)
                elif system == 'Darwin':  # macOS
                    subprocess.run(['open', logs_dir])
                else:  # Linux and other Unix-like systems
                    subprocess.run(['xdg-open', logs_dir])
                
                logger.info(f"Opened logs directory: {logs_dir}")
            except Exception as e:
                messagebox.showerror("Error", 
                                   f"Failed to open logs directory:\n{str(e)}\n\n"
                                   f"Please manually open:\n{logs_dir}")
                logger.error(f"Failed to open logs directory: {str(e)}", exc_info=True)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open logs directory: {str(e)}")
            logger.error(f"Log viewer error: {str(e)}", exc_info=True)


def main():
    root = tk.Tk()
    app = FieldMapperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

