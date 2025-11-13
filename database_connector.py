"""
Database Connector Module
Handles connections to various database types and extracts table field information
"""

from typing import List, Dict, Optional
import logging

# Import database connectors (optional - only import if available)
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pyodbc
    SQLSERVER_AVAILABLE = True
except ImportError:
    SQLSERVER_AVAILABLE = False

try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

try:
    import cx_Oracle
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnector:
    def __init__(self):
        self.connection = None
        self.db_type = None
    
    def connect(self, db_type: str, host: str, port: str, database: str, 
                username: str, password: str):
        """Connect to database based on type"""
        self.db_type = db_type
        
        try:
            if db_type == "MySQL":
                if not MYSQL_AVAILABLE:
                    raise ImportError("mysql-connector-python is not installed. Install it with: pip install mysql-connector-python")
                self.connection = mysql.connector.connect(
                    host=host,
                    port=int(port) if port else 3306,
                    database=database,
                    user=username,
                    password=password
                )
            
            elif db_type == "PostgreSQL":
                if not POSTGRESQL_AVAILABLE:
                    raise ImportError("psycopg2 is not installed. Install it with: pip install psycopg2-binary")
                self.connection = psycopg2.connect(
                    host=host,
                    port=int(port) if port else 5432,
                    database=database,
                    user=username,
                    password=password
                )
            
            elif db_type == "SQL Server":
                if not SQLSERVER_AVAILABLE:
                    raise ImportError("pyodbc is not installed. Install it with: pip install pyodbc")
                conn_string = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={host},{port if port else 1433};"
                    f"DATABASE={database};"
                    f"UID={username};"
                    f"PWD={password}"
                )
                self.connection = pyodbc.connect(conn_string)
            
            elif db_type == "SQLite":
                if not SQLITE_AVAILABLE:
                    raise ImportError("sqlite3 should be available with Python. If not, there's an issue with your Python installation.")
                # For SQLite, host is the file path
                self.connection = sqlite3.connect(host if host else database)
            
            elif db_type == "Oracle":
                if not ORACLE_AVAILABLE:
                    raise ImportError("cx_Oracle is not installed. Install it with: pip install cx_Oracle")
                dsn = cx_Oracle.makedsn(host, int(port) if port else 1521, 
                                       service_name=database)
                self.connection = cx_Oracle.connect(username, password, dsn)
            
            else:
                raise ValueError(f"Unsupported database type: {db_type}")
            
            logger.info(f"Successfully connected to {db_type} database")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def get_table_fields(self, table_name: str) -> List[str]:
        """Get field names from a database table"""
        if not self.connection:
            raise ConnectionError("Not connected to database")
        
        fields = []
        
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "MySQL":
                query = f"DESCRIBE `{table_name}`"
                cursor.execute(query)
                results = cursor.fetchall()
                fields = [row[0] for row in results]
            
            elif self.db_type == "PostgreSQL":
                query = """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """
                cursor.execute(query, (table_name,))
                results = cursor.fetchall()
                fields = [row[0] for row in results]
            
            elif self.db_type == "SQL Server":
                query = """
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """
                cursor.execute(query, (table_name,))
                results = cursor.fetchall()
                fields = [row[0] for row in results]
            
            elif self.db_type == "SQLite":
                query = f"PRAGMA table_info({table_name})"
                cursor.execute(query)
                results = cursor.fetchall()
                fields = [row[1] for row in results]
            
            elif self.db_type == "Oracle":
                query = """
                    SELECT column_name 
                    FROM user_tab_columns 
                    WHERE table_name = UPPER(:table_name)
                    ORDER BY column_id
                """
                cursor.execute(query, {'table_name': table_name})
                results = cursor.fetchall()
                fields = [row[0] for row in results]
            
            cursor.close()
            logger.info(f"Retrieved {len(fields)} fields from table {table_name}")
            
            return fields
            
        except Exception as e:
            logger.error(f"Failed to get table fields: {str(e)}")
            raise
    
    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        if not self.connection:
            raise ConnectionError("Not connected to database")
        
        tables = []
        
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "MySQL":
                query = "SHOW TABLES"
                cursor.execute(query)
                results = cursor.fetchall()
                tables = [row[0] for row in results]
            
            elif self.db_type == "PostgreSQL":
                query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """
                cursor.execute(query)
                results = cursor.fetchall()
                tables = [row[0] for row in results]
            
            elif self.db_type == "SQL Server":
                query = """
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE'
                """
                cursor.execute(query)
                results = cursor.fetchall()
                tables = [row[0] for row in results]
            
            elif self.db_type == "SQLite":
                query = "SELECT name FROM sqlite_master WHERE type='table'"
                cursor.execute(query)
                results = cursor.fetchall()
                tables = [row[0] for row in results]
            
            elif self.db_type == "Oracle":
                query = "SELECT table_name FROM user_tables"
                cursor.execute(query)
                results = cursor.fetchall()
                tables = [row[0] for row in results]
            
            cursor.close()
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get tables: {str(e)}")
            raise
    
    def get_field_details(self, table_name: str) -> List[Dict]:
        """Get detailed field information including data types"""
        if not self.connection:
            raise ConnectionError("Not connected to database")
        
        fields = []
        
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "MySQL":
                query = f"DESCRIBE `{table_name}`"
                cursor.execute(query)
                results = cursor.fetchall()
                fields = [
                    {
                        'name': row[0],
                        'type': row[1],
                        'null': row[2],
                        'key': row[3],
                        'default': row[4],
                        'extra': row[5]
                    }
                    for row in results
                ]
            
            elif self.db_type == "PostgreSQL":
                query = """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """
                cursor.execute(query, (table_name,))
                results = cursor.fetchall()
                fields = [
                    {
                        'name': row[0],
                        'type': row[1],
                        'nullable': row[2],
                        'default': row[3]
                    }
                    for row in results
                ]
            
            # Similar implementations for other database types...
            
            cursor.close()
            return fields
            
        except Exception as e:
            logger.error(f"Failed to get field details: {str(e)}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

