"""Pure SQLite connection wrapper. No table knowledge."""
import os
import sqlite3
import pandas as pd


class Connection:
    """Low-level SQLite connection provider. It creates new connections every time to support concurrent access as used by Dash"""
    
    def __init__(self, data_file: str = "beerbase.db"):
        self.data_file = data_file
    
    def connect(self):
        """Establish database connection and return (con, cur)."""
        if self.data_file != ":memory:" and not os.path.exists(self.data_file):
            open(self.data_file, "w")
        
        con = sqlite3.connect(self.data_file)
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
