"""
Database connection management module for the Role-Based Attendance System.

This module provides database connection utilities using pyodbc for SQL Server,
including connection management, error handling, and query execution functions.

Requirements: 1.3, 1.4, 13.3, 15.1
"""

import os
import pyodbc
from typing import Optional, List, Tuple, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_db_connection() -> pyodbc.Connection:
    """
    Establish and return a connection to the SQL Server database.
    
    Connection parameters are loaded from environment variables:
    - SERVER: SQL Server hostname or IP address
    - DATABASE: Database name
    - UID: Username for authentication
    - PWD: Password for authentication
    - DRIVER: ODBC driver (optional, defaults to 'ODBC Driver 17 for SQL Server')
    
    Returns:
        pyodbc.Connection: Active database connection object
        
    Raises:
        ValueError: If required environment variables are missing
        pyodbc.Error: If connection to database fails
        
    Example:
        >>> conn = get_db_connection()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT * FROM Login_Master")
    """
    # Retrieve connection parameters from environment variables
    server = os.getenv('SERVER')
    database = os.getenv('DATABASE')
    uid = os.getenv('UID')
    pwd = os.getenv('PWD')
    driver = os.getenv('DRIVER', '{ODBC Driver 17 for SQL Server}')
    
    # Validate that all required parameters are present
    missing_params = []
    if not server:
        missing_params.append('SERVER')
    if not database:
        missing_params.append('DATABASE')
    if not uid:
        missing_params.append('UID')
    if not pwd:
        missing_params.append('PWD')
    
    if missing_params:
        raise ValueError(
            f"Missing required database connection parameters: {', '.join(missing_params)}. "
            f"Please ensure these environment variables are set in your .env file."
        )
    
    # Construct connection string
    connection_string = (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={uid};"
        f"PWD={pwd};"
    )
    
    try:
        # Establish connection
        connection = pyodbc.connect(connection_string)
        return connection
    except pyodbc.Error as e:
        # Provide descriptive error message for connection failures
        error_message = str(e)
        raise pyodbc.Error(
            f"Failed to connect to database '{database}' on server '{server}'. "
            f"Error details: {error_message}"
        )


def execute_query(
    query: str,
    params: Optional[Tuple[Any, ...]] = None,
    fetch: bool = True
) -> Optional[List[pyodbc.Row]]:
    """
    Execute a SQL query with automatic connection management and error handling.
    
    This utility function handles connection creation, query execution, and
    proper resource cleanup. It supports both SELECT queries (with fetch=True)
    and INSERT/UPDATE/DELETE queries (with fetch=False).
    
    Args:
        query: SQL query string to execute (supports parameterized queries with ?)
        params: Optional tuple of parameters for parameterized queries
        fetch: If True, fetch and return results (for SELECT queries).
               If False, commit changes and return None (for INSERT/UPDATE/DELETE)
    
    Returns:
        List[pyodbc.Row]: Query results if fetch=True, None otherwise
        
    Raises:
        pyodbc.Error: If query execution fails
        ValueError: If connection parameters are missing
        
    Examples:
        # SELECT query
        >>> results = execute_query("SELECT * FROM Login_Master WHERE username = ?", ("admin",))
        >>> for row in results:
        ...     print(row.username, row.privilege_level)
        
        # INSERT query
        >>> execute_query(
        ...     "INSERT INTO Student_Master (prn, name, panel) VALUES (?, ?, ?)",
        ...     ("PRN001", "John Doe", "A"),
        ...     fetch=False
        ... )
    """
    connection = None
    cursor = None
    
    try:
        # Establish database connection
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Execute query with or without parameters
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # Handle result fetching or commit based on query type
        if fetch:
            # Fetch all results for SELECT queries
            results = cursor.fetchall()
            return results
        else:
            # Commit changes for INSERT/UPDATE/DELETE queries
            connection.commit()
            return None
            
    except pyodbc.Error as e:
        # Rollback transaction on error
        if connection:
            connection.rollback()
        
        # Provide descriptive error message
        error_message = str(e)
        raise pyodbc.Error(
            f"Query execution failed. Query: {query[:100]}... "
            f"Error details: {error_message}"
        )
    
    finally:
        # Ensure resources are properly cleaned up
        if cursor:
            cursor.close()
        if connection:
            connection.close()
