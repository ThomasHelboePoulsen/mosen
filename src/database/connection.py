"""Pure SQLite connection wrapper. No table knowledge."""
import os
import sqlite3
from threading import RLock
import pandas as pd


class Connection:
    """Low-level SQLite connection provider. It creates new connections every time to support concurrent access as used by Dash
    Callers need to manage the lock themselves. This is currently done by tables, if you use this directly you risk data loss"""
    
    def __init__(self, data_file: str = "beerbase.db"):
        self.data_file = data_file
        self._lock = RLock()
       
    def connect(self):
        """Establish database connection and return (con, cur)."""
        con = sqlite3.connect(self.data_file, timeout=5)
        return con, con.cursor()

    
    def execute(self, query: str) -> list:
        """Execute raw SQL and return results."""
        con, cur = self.connect()
        result = cur.execute(query).fetchall()
        con.close()
        return result
    
    def execute_commit(self, query: str):
        """Execute SQL and commit."""
        con, cur = self.connect()
        cur.execute(query)
        con.commit()
        con.close()
    
    def get_query(self, query: str, columns: list) -> pd.DataFrame:
        """Execute query and return DataFrame with string columns."""
        con, cur = self.connect()
        data = pd.DataFrame(cur.execute(query), columns=columns, dtype=str)
        con.close()
        return data
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        con, cur = self.connect()
        result = cur.execute(sql, (table_name,)).fetchone() is not None
        con.close()
        return result
    
    def init(self):
        """Get connection (backward compatibility with Database.init())."""
        return self.connect()
