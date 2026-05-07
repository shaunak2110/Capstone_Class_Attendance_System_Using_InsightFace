"""
Unit tests for database.py module.

Tests cover connection management, error handling, and query execution utilities.
"""

import pytest
import os
import pyodbc
from unittest.mock import patch, MagicMock
from database import get_db_connection, execute_query


class TestGetDbConnection:
    """Test suite for get_db_connection function."""

    @patch('database.pyodbc.connect')
    def test_db_connection_string_used_directly(self, mock_connect):
        """When DB_CONNECTION_STRING is set, it is passed directly to pyodbc.connect."""
        mock_connect.return_value = MagicMock()
        conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=myserver.database.windows.net;DATABASE=AttendanceDB;UID=user;PWD=pass;Encrypt=yes'

        with patch.dict(os.environ, {'DB_CONNECTION_STRING': conn_str}, clear=True):
            get_db_connection()
            mock_connect.assert_called_once_with(conn_str)

    @patch('database.pyodbc.connect')
    def test_db_connection_string_no_trusted_connection(self, mock_connect):
        """When DB_CONNECTION_STRING is set, Trusted_Connection must NOT be appended."""
        mock_connect.return_value = MagicMock()
        conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=myserver.database.windows.net;DATABASE=AttendanceDB;UID=user;PWD=pass'

        with patch.dict(os.environ, {'DB_CONNECTION_STRING': conn_str}, clear=True):
            get_db_connection()
            call_arg = mock_connect.call_args[0][0]
            assert 'Trusted_Connection' not in call_arg

    @patch('database.pyodbc.connect')
    def test_db_connection_string_failure_descriptive_error(self, mock_connect):
        """When DB_CONNECTION_STRING is set but connection fails, error message is descriptive."""
        mock_connect.side_effect = pyodbc.Error("Login failed")
        conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=bad;DATABASE=db;UID=u;PWD=p'

        with patch.dict(os.environ, {'DB_CONNECTION_STRING': conn_str}, clear=True):
            with pytest.raises(pyodbc.Error) as exc_info:
                get_db_connection()
            assert 'DB_CONNECTION_STRING' in str(exc_info.value)
            assert 'Login failed' in str(exc_info.value)

    def test_missing_server_parameter(self):
        """Test that missing SERVER environment variable raises ValueError (Windows Auth fallback)."""
        with patch.dict(os.environ, {'DATABASE': 'test_db'}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_db_connection()
            assert 'SERVER' in str(exc_info.value)
            assert 'Missing required database parameters' in str(exc_info.value)

    def test_missing_database_parameter(self):
        """Test that missing DATABASE environment variable raises ValueError (Windows Auth fallback)."""
        with patch.dict(os.environ, {'SERVER': 'test_server'}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_db_connection()
            assert 'DATABASE' in str(exc_info.value)

    def test_missing_multiple_parameters(self):
        """Test that missing SERVER and DATABASE lists both in the error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_db_connection()
            error_msg = str(exc_info.value)
            assert 'SERVER' in error_msg
            assert 'DATABASE' in error_msg

    @patch('database.pyodbc.connect')
    def test_windows_auth_fallback_uses_trusted_connection(self, mock_connect):
        """When DB_CONNECTION_STRING is absent, connection string uses Trusted_Connection=yes."""
        mock_connect.return_value = MagicMock()

        with patch.dict(os.environ, {
            'SERVER': 'test_server',
            'DATABASE': 'test_db',
        }, clear=True):
            conn = get_db_connection()

            assert conn == mock_connect.return_value
            connection_string = mock_connect.call_args[0][0]
            assert 'Trusted_Connection=yes' in connection_string
            assert 'SERVER=test_server' in connection_string
            assert 'DATABASE=test_db' in connection_string
            assert 'DRIVER={ODBC Driver 17 for SQL Server}' in connection_string

    @patch('database.pyodbc.connect')
    def test_successful_connection_with_custom_driver(self, mock_connect):
        """Test successful connection with custom ODBC driver in Windows Auth fallback."""
        mock_connect.return_value = MagicMock()

        with patch.dict(os.environ, {
            'SERVER': 'test_server',
            'DATABASE': 'test_db',
            'DRIVER': '{ODBC Driver 18 for SQL Server}'
        }, clear=True):
            get_db_connection()

            connection_string = mock_connect.call_args[0][0]
            assert 'DRIVER={ODBC Driver 18 for SQL Server}' in connection_string

    @patch('database.pyodbc.connect')
    def test_windows_auth_connection_failure_descriptive_error(self, mock_connect):
        """Test that Windows Auth connection failures provide descriptive error messages."""
        mock_connect.side_effect = pyodbc.Error("Connection timeout")

        with patch.dict(os.environ, {
            'SERVER': 'invalid_server',
            'DATABASE': 'test_db',
        }, clear=True):
            with pytest.raises(pyodbc.Error) as exc_info:
                get_db_connection()

            error_msg = str(exc_info.value)
            assert 'Failed to connect to database' in error_msg
            assert 'test_db' in error_msg
            assert 'invalid_server' in error_msg
            assert 'Connection timeout' in error_msg


class TestExecuteQuery:
    """Test suite for execute_query function."""
    
    @patch('database.get_db_connection')
    def test_select_query_with_results(self, mock_get_connection):
        """Test SELECT query returns fetched results."""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Mock query results
        mock_row1 = MagicMock()
        mock_row1.username = 'user1'
        mock_row2 = MagicMock()
        mock_row2.username = 'user2'
        mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
        
        # Execute query
        results = execute_query("SELECT * FROM Login_Master")
        
        # Verify
        assert len(results) == 2
        assert results[0].username == 'user1'
        assert results[1].username == 'user2'
        mock_cursor.execute.assert_called_once_with("SELECT * FROM Login_Master")
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('database.get_db_connection')
    def test_select_query_with_parameters(self, mock_get_connection):
        """Test parameterized SELECT query."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchall.return_value = []
        
        query = "SELECT * FROM Login_Master WHERE username = ?"
        params = ("admin",)
        execute_query(query, params)
        
        mock_cursor.execute.assert_called_once_with(query, params)
    
    @patch('database.get_db_connection')
    def test_insert_query_commits_changes(self, mock_get_connection):
        """Test INSERT query commits changes and returns None."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        query = "INSERT INTO Student_Master (prn, name, panel) VALUES (?, ?, ?)"
        params = ("PRN001", "John Doe", "A")
        result = execute_query(query, params, fetch=False)
        
        assert result is None
        mock_cursor.execute.assert_called_once_with(query, params)
        mock_connection.commit.assert_called_once()
        mock_cursor.fetchall.assert_not_called()
    
    @patch('database.get_db_connection')
    def test_update_query_commits_changes(self, mock_get_connection):
        """Test UPDATE query commits changes."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        query = "UPDATE Login_Master SET privilege_level = ? WHERE user_id = ?"
        params = (2, 5)
        execute_query(query, params, fetch=False)
        
        mock_connection.commit.assert_called_once()
    
    @patch('database.get_db_connection')
    def test_query_execution_error_rolls_back(self, mock_get_connection):
        """Test that query errors trigger rollback."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Simulate query execution error
        mock_cursor.execute.side_effect = pyodbc.Error("Syntax error")
        
        with pytest.raises(pyodbc.Error) as exc_info:
            execute_query("INVALID SQL QUERY")
        
        # Verify rollback was called
        mock_connection.rollback.assert_called_once()
        error_msg = str(exc_info.value)
        assert 'Query failed' in error_msg
        assert 'Syntax error' in error_msg
    
    @patch('database.get_db_connection')
    def test_resources_cleaned_up_on_success(self, mock_get_connection):
        """Test that cursor and connection are closed after successful query."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchall.return_value = []
        
        execute_query("SELECT * FROM Login_Master")
        
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('database.get_db_connection')
    def test_resources_cleaned_up_on_error(self, mock_get_connection):
        """Test that cursor and connection are closed even when query fails."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        mock_cursor.execute.side_effect = pyodbc.Error("Error")
        
        with pytest.raises(pyodbc.Error):
            execute_query("SELECT * FROM Login_Master")
        
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('database.get_db_connection')
    def test_empty_result_set(self, mock_get_connection):
        """Test query with no results returns empty list."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchall.return_value = []
        
        results = execute_query("SELECT * FROM Login_Master WHERE user_id = ?", (9999,))
        
        assert results == []
        assert isinstance(results, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# ---------------------------------------------------------------------------
# Property-Based Tests
# Feature: cloud-deployment, Property 2: Database connection string selection
# Validates: Requirements 3.1, 3.2, 3.3
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st


@given(conn_str=st.text(min_size=1, max_size=500).filter(lambda s: s.strip()))
@settings(max_examples=100)
def test_pbt_db_connection_string_used_directly(conn_str):
    """
    Property 2: For any non-empty DB_CONNECTION_STRING, get_db_connection()
    calls pyodbc.connect with exactly that string.

    **Validates: Requirements 3.1, 3.2**
    """
    with patch('database.os.getenv') as mock_getenv, \
         patch('database.pyodbc.connect', return_value=MagicMock()) as mock_connect:
        # DB_CONNECTION_STRING returns conn_str; all other keys return None
        mock_getenv.side_effect = lambda key, *args: conn_str if key == 'DB_CONNECTION_STRING' else (args[0] if args else None)
        from database import get_db_connection
        get_db_connection()
        mock_connect.assert_called_once_with(conn_str)


@given(
    server=st.from_regex(r'[A-Za-z0-9._\\-]{1,50}', fullmatch=True),
    db_name=st.from_regex(r'[A-Za-z0-9_]{1,50}', fullmatch=True),
)
@settings(max_examples=100)
def test_pbt_windows_auth_fallback_contains_trusted_connection(server, db_name):
    """
    Property 2 (fallback): When DB_CONNECTION_STRING is absent, the constructed
    connection string must contain Trusted_Connection=yes.

    **Validates: Requirements 3.3**
    """
    def mock_getenv(key, *args):
        mapping = {
            'SERVER': server,
            'DATABASE': db_name,
            'DRIVER': '{ODBC Driver 17 for SQL Server}',
        }
        if key == 'DB_CONNECTION_STRING':
            return None
        return mapping.get(key, args[0] if args else None)

    with patch('database.os.getenv', side_effect=mock_getenv), \
         patch('database.pyodbc.connect', return_value=MagicMock()) as mock_connect:
        from database import get_db_connection
        get_db_connection()
        call_args = mock_connect.call_args[0][0]
        assert 'Trusted_Connection=yes' in call_args
