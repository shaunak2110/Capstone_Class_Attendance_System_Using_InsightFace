"""
Database connection management module (pymssql / Azure SQL).

Uses pymssql so we don't need the Microsoft ODBC driver installed at the OS
level — works on plain Linux containers (Render Python runtime).
"""

import os
import re
import time
import logging
import pymssql
from typing import Optional, List, Tuple, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Azure SQL transient error codes that signal "retry, the DB is waking up".
_TRANSIENT_CODES = ("40613", "40197", "40501", "49918", "49919", "49920", "10928", "10929")


def _is_transient_error(exc: pymssql.Error) -> bool:
    msg = str(exc)
    if any(code in msg for code in _TRANSIENT_CODES):
        return True
    if "Adaptive Server connection failed" in msg:
        return True
    return False


def _connect_with_retry(max_attempts: int = 4, **kwargs):
    """pymssql.connect with backoff on Azure SQL Serverless warm-up errors."""
    for attempt in range(max_attempts):
        try:
            return _RowConnection(pymssql.connect(**kwargs))
        except pymssql.Error as e:
            if attempt == max_attempts - 1 or not _is_transient_error(e):
                raise
            wait = 3 * (2 ** attempt)  # 3s, 6s, 12s
            logger.warning(
                "DB connect transient error (attempt %d/%d): %s. Retrying in %ds.",
                attempt + 1, max_attempts, e, wait,
            )
            time.sleep(wait)


# ---------------------------------------------------------------------------
# pyodbc.Row compatibility layer
#
# pyodbc returns rows that support both index access (row[0]) and attribute
# access (row.user_id). pymssql returns plain tuples. The route handlers across
# auth.py / admin.py / user.py rely on row.column_name. Wrap pymssql cursors so
# fetchall/fetchone return objects that support both shapes.
# ---------------------------------------------------------------------------

class _Row:
    __slots__ = ("_cols", "_values")

    def __init__(self, cols, values):
        object.__setattr__(self, "_cols", cols)
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name):
        cols = object.__getattribute__(self, "_cols")
        try:
            i = cols.index(name)
        except ValueError:
            raise AttributeError(name)
        return self._values[i]

    def __getitem__(self, key):
        if isinstance(key, str):
            return getattr(self, key)
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._cols, self._values))})"


class _RowCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def _wrap_one(self, row):
        if row is None or not self._cursor.description:
            return row
        cols = [d[0] for d in self._cursor.description]
        return _Row(cols, row)

    def execute(self, *args, **kwargs):
        return self._cursor.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._cursor.executemany(*args, **kwargs)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows or not self._cursor.description:
            return rows
        cols = [d[0] for d in self._cursor.description]
        return [_Row(cols, r) for r in rows]

    def fetchone(self):
        return self._wrap_one(self._cursor.fetchone())

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        if not rows or not self._cursor.description:
            return rows
        cols = [d[0] for d in self._cursor.description]
        return [_Row(cols, r) for r in rows]

    def close(self):
        return self._cursor.close()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class _RowConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        return _RowCursor(self._conn.cursor(*args, **kwargs))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _parse_connection_string(conn_str: str) -> dict:
    """
    Parse a SQL Server-style connection string (DRIVER=...;SERVER=...;DATABASE=...;UID=...;PWD=...)
    into pymssql.connect kwargs.

    Accepts both ODBC-style ("SERVER=host,1433") and host-only forms.
    """
    parts = {}
    for piece in conn_str.split(";"):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        key, _, val = piece.partition("=")
        val = val.strip()
        # Strip ODBC-style braces around values (e.g. Pwd={p@ss;word}).
        if len(val) >= 2 and val.startswith("{") and val.endswith("}"):
            val = val[1:-1]
        parts[key.strip().lower()] = val

    server = parts.get("server", "")
    port = None
    if "," in server:
        server, port_str = server.rsplit(",", 1)
        port = int(port_str)
    server = re.sub(r"^tcp:", "", server)

    kwargs = {
        "server": server,
        "user": parts.get("uid") or parts.get("user id") or parts.get("user"),
        "password": parts.get("pwd") or parts.get("password"),
        "database": parts.get("database") or parts.get("initial catalog"),
    }
    if port:
        kwargs["port"] = port
    return {k: v for k, v in kwargs.items() if v is not None}


def get_db_connection():
    """
    Connect to SQL Server / Azure SQL via pymssql.

    Preferred: DB_CONNECTION_STRING (ODBC-style or pymssql-friendly).
    Fallback: SERVER, DATABASE, DB_USER, DB_PASSWORD env vars (cloud).
    """
    conn_str = os.getenv("DB_CONNECTION_STRING")
    if conn_str:
        try:
            return _connect_with_retry(**_parse_connection_string(conn_str))
        except pymssql.Error as e:
            raise pymssql.Error(
                f"Failed to connect using DB_CONNECTION_STRING. Error: {str(e)}"
            )

    server = os.getenv("SERVER")
    database = os.getenv("DATABASE")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    missing = [k for k, v in {
        "SERVER": server, "DATABASE": database,
        "DB_USER": user, "DB_PASSWORD": password,
    }.items() if not v]
    if missing:
        raise ValueError(
            f"Missing required database parameters: {', '.join(missing)}. "
            f"Set DB_CONNECTION_STRING or SERVER/DATABASE/DB_USER/DB_PASSWORD."
        )

    try:
        return _connect_with_retry(
            server=server, user=user, password=password, database=database
        )
    except pymssql.Error as e:
        raise pymssql.Error(
            f"Failed to connect to database '{database}' on server '{server}'. "
            f"Error: {str(e)}"
        )


def execute_query(
    query: str,
    params: Optional[Tuple[Any, ...]] = None,
    fetch: bool = True,
) -> Optional[List[Tuple[Any, ...]]]:
    """Execute SQL query safely. Use %s for parameter placeholders (pymssql paramstyle)."""
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
        connection.commit()
        return None
    except pymssql.Error as e:
        if connection:
            connection.rollback()
        raise pymssql.Error(f"Query failed: {query[:100]}... | Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
