"""
db_handler.py

This module provides a generic interface for interacting with a PostgreSQL database. 
It includes functionalities to connect to the database, execute SQL queries, fetch results, 
and close the connection.

Example:
    from db_handler import DBHandler
    db = DBHandler(dbname="sample_db", user="user", password="password")
    db.connect()
    results = db.fetch("SELECT * FROM sample_table")
    db.close()
"""

import psycopg2

class DBHandler:
    """
    A handler for database operations on a PostgreSQL database.
    
    This class provides methods to connect to a PostgreSQL database, execute SQL commands,
    fetch data from the database, and close the connection. It's designed to be a flexible and
    reusable component for database operations.
    
    Attributes:
        dbname (str): Name of the database.
        user (str): Database user name.
        password (str): Password for the database user.
        host (str, optional): Host of the database. Defaults to "localhost".
        port (str, optional): Port to connect on. Defaults to "5432".
        conn (psycopg2.extensions.connection): The database connection object.
    
    Example:
        db_handler = DBHandler(dbname="mydb", user="user", password="pass")
        db_handler.connect()
        db_handler.execute("INSERT INTO table_name (column1, column2) VALUES (value1, value2)")
        results = db_handler.fetch("SELECT * FROM table_name")
        db_handler.close()
    """
    # pylint: disable=too-many-arguments
    def __init__(self, dbname, user, password, host="localhost", port="5432"):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None

    def connect(self):
        """Establish a connection to the database."""
        self.conn = psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )
        return self.conn

    def execute(self, query, params=None):
        """Execute a SQL query."""
        with self.conn.cursor() as cur:
            cur.execute(query, params)
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