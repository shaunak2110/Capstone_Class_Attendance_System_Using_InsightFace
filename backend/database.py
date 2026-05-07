"""
Database connection management module (Windows Authentication version)
"""

import os
import pyodbc
from typing import Optional, List, Tuple, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_db_connection() -> pyodbc.Connection:
    """
    Connect to SQL Server.

    If DB_CONNECTION_STRING is set, use it directly as the pyodbc connection
    string (supports Azure SQL and any other SQL Server variant).

    Otherwise fall back to Windows Authentication for local development,
    reading SERVER, DATABASE, and DRIVER from the environment.
    """

    conn_str = os.getenv('DB_CONNECTION_STRING')
    if conn_str:
        try:
            return pyodbc.connect(conn_str)
        except pyodbc.Error as e:
            raise pyodbc.Error(
                f"Failed to connect using DB_CONNECTION_STRING. Error: {str(e)}"
            )

    # Fallback: Windows Authentication for local development
    server = os.getenv('SERVER')
    database = os.getenv('DATABASE')
    driver = os.getenv('DRIVER', '{ODBC Driver 17 for SQL Server}')

    missing = []
    if not server:
        missing.append("SERVER")
    if not database:
        missing.append("DATABASE")

    if missing:
        raise ValueError(
            f"Missing required database parameters: {', '.join(missing)}. "
            f"Check your .env file."
        )

    # Windows Authentication connection string
    connection_string = (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
    )

    try:
        return pyodbc.connect(connection_string)

    except pyodbc.Error as e:
        raise pyodbc.Error(
            f"Failed to connect to database '{database}' on server '{server}'. "
            f"Error: {str(e)}"
        )


def execute_query(
    query: str,
    params: Optional[Tuple[Any, ...]] = None,
    fetch: bool = True
) -> Optional[List[pyodbc.Row]]:
    """
    Execute SQL query safely
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch:
            return cursor.fetchall()
        else:
            connection.commit()
            return None

    except pyodbc.Error as e:
        if connection:
            connection.rollback()

        raise pyodbc.Error(
            f"Query failed: {query[:100]}... | Error: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()