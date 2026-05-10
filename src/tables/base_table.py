from abc import ABC, abstractmethod
import pandas as pd
from src.connection import Connection

class BaseTable(ABC):
    """Abstract base for all table operations."""
    
    table_name: str      # Override: "prods", "users", etc
    columns: dict        # Override: {"barcode": int, "name": str, ...}
    create_sql: str      # Override: SQL to create table
    
    def __init__(self, connection: Connection):
        self.connection = connection
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create table if it doesn't exist."""
        if not self.connection.table_exists(self.table_name):
            con, _ = self.connection.connect()
            con.execute(self.create_sql)
            con.commit()
            con.close()
    
    def validate_columns(self, row: dict) -> bool:
        """Check required columns exist. Returns True if bad."""
        return set(row.keys()) != set(self.columns.keys())
    
    @abstractmethod
    def validate(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Subclass implements validation. Returns (row, is_bad)."""
        raise NotImplementedError
    
    def get(self) -> pd.DataFrame:
        """Return all rows as strings."""
        query = f"SELECT * FROM {self.table_name}"
        return self.connection.get_query(query, list(self.columns.keys()))
    
    def get_typed(self) -> pd.DataFrame:
        """Return all rows with correct Python types."""
        df = self.get()
        if df.empty:
            return pd.DataFrame({col: pd.Series([], dtype=dtype) 
                               for col, dtype in self.columns.items()})
        for col, dtype in self.columns.items():
            df[col] = df[col].astype(dtype)
        return df
    
    def set(self, data: list | pd.DataFrame) -> tuple[str, list]:
        """Replace mode: delete all, validate, insert."""
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient="records")
        
        con, cur = self.connection.connect()
        bad_rows = []
        good_rows = []
        
        for row in data:
            if self.validate_columns(row):
                bad_rows.append(row)
                continue
            
            row, is_bad = self.validate(row, data)
            
            for col, val in row.items():
                if val is None or str(val).strip() == "":
                    row[col] = "Unknown"
                    is_bad = True
            
            if is_bad:
                bad_rows.append(row)
            else:
                good_rows.append(row)
        
        if bad_rows:
            con.close()
            return self.table_name, bad_rows
        
        cur.execute(f"DELETE FROM {self.table_name}")
        if good_rows:
            cols = ", ".join(good_rows[0].keys())
            placeholders = ", ".join(["?" for _ in good_rows[0].keys()])
            cur.executemany(f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders})", 
                           [list(row.values()) for row in good_rows])
        
        con.commit()
        con.close()
        
        return "success", bad_rows
