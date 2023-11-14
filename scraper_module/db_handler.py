"""
db_handler.py

This module provides a generic interface for interacting with a SQL Server database. 
It supports both Windows Authentication and SQL Server Authentication. The module 
includes functionality to connect to the database, execute SQL queries, fetch results, 
and close the connection.

The module uses an enum `AuthMethod` to specify the authentication method.

Example:
    from db_handler import DBHandler, AuthMethod

    # For Windows Authentication
    db = DBHandler(dbname="sample_db", auth_method=AuthMethod.WINDOWS_AUTH)
    db.connect()
    results = db.fetch("SELECT * FROM sample_table")
    db.close()

    # For SQL Server Authentication
    db = DBHandler(dbname="sample_db", auth_method=AuthMethod.SQL_SERVER_AUTH, user="user", password="password")
    db.connect()
    results = db.fetch("SELECT * FROM sample_table")
    db.close()
"""


import pyodbc

from .auth_method import AuthMethod

class DBHandler:
    """
    A handler for database operations on a SQL Server database.
    
    This class provides methods to connect to a SQL Server database, execute SQL commands,
    fetch data from the database, and close the connection. It supports both Windows 
    Authentication and SQL Server Authentication, determined by the `auth_method` parameter.

    Attributes:
        dbname (str): Name of the database.
        auth_method (AuthMethod): The method of authentication to use (Windows or SQL Server).
        user (str, optional): Database user name. Required if using SQL Server Authentication.
        password (str, optional): Password for the database user. Required if using SQL Server Authentication.
        host (str, optional): Host of the database. Defaults to "localhost".
        port (str, optional): Port to connect on. Defaults to "1433".
        conn (pyodbc.Connection): The database connection object.

    Example for Windows Authentication:
        db_handler = DBHandler(dbname="mydb", auth_method=AuthMethod.WINDOWS_AUTH)
        db_handler.connect()
        results = db_handler.fetch("SELECT * FROM table_name")
        db_handler.close()

    Example for SQL Server Authentication:
        db_handler = DBHandler(dbname="mydb", auth_method=AuthMethod.SQL_SERVER_AUTH, user="user", password="pass")
        db_handler.connect()
        results = db_handler.fetch("SELECT * FROM table_name")
        db_handler.close()
    """

    # pylint: disable=too-many-arguments
    def __init__(self, dbname, auth_method=AuthMethod.WINDOWS_AUTH, host="localhost", port="1433", user=None, password=None):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.auth_method = auth_method
        self.conn = None

    def connect(self):
        """Establish a connection to the database."""
        if self.auth_method == AuthMethod.SQL_SERVER_AUTH and self.user and self.password:
            # SQL Server Authentication
            connection_string = f'DRIVER={{SQL Server}};SERVER={self.host};DATABASE={self.dbname};UID={self.user};PWD={self.password}'
            self.conn = pyodbc.connect(connection_string)
        elif self.auth_method == AuthMethod.WINDOWS_AUTH:
            # Windows Authentication
            connection_string = f'DRIVER={{SQL Server}};SERVER={self.host};DATABASE={self.dbname};Trusted_Connection=yes;'
            self.conn = pyodbc.connect(connection_string)
        else:
            raise ValueError("Invalid authentication method or credentials")
        return self.conn

    def execute(self, query, params=None):
        """Execute a SQL query."""
        with self.conn.cursor() as cur:
            if params is not None:
                cur.execute(query, params)
            else:
                cur.execute(query)
            self.conn.commit()

    def fetch(self, query, params=None):
        """Fetch results from a SQL query."""
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()