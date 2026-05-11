from abc import ABC, abstractmethod
import pandas as pd
from src.connection import Connection
from src.tables.column import Column,BarcodeColumn

class BaseTable(ABC):
    """Abstract base for all table operations."""
    
    table_name: str      # Override: "prods", "users", etc
    columns: list        # Override: list of Column objects
    create_sql: str      # Override: SQL to create table
    
    def __init__(self, connection: Connection):
        self.connection = connection
        self._ensure_table_exists()
    
    @property
    def primary_keys(self) -> list:
        """Return list of primary key column names."""
        return [col.name for col in self.columns if col.is_primary_key]
    
    def validate_columns(self, row: dict) -> bool:
        """Check that all present columns are valid and all required columns exist.
        Returns True if the row is valid (helper method for testing)."""
        valid_col_names = {col.name for col in self.columns}
        
        for col_name in row.keys():
            if col_name not in valid_col_names:
                return False
        
        for col in self.columns:
            if col.required and col.name not in row:
                return False
        
        return True
    
    def _check_primary_key_duplicates(self, row: dict, all_rows: list) -> bool:
        """Check if the complete composite primary key is duplicated.
        Returns True if this exact combination of all primary keys already exists, False otherwise."""
        
        if not self.primary_keys:
            return False
        
        df = pd.DataFrame(all_rows)
        
        mask = pd.Series([True] * len(df))
        for pk_col in self.primary_keys:
            mask = mask & (df[pk_col] == row[pk_col])
        
        return sum(mask) > 1
    
    def _ensure_table_exists(self):
        """Create table if it doesn't exist."""
        if not self.connection.table_exists(self.table_name):
            con, _ = self.connection.connect()
            con.execute(self.create_sql)
            con.commit()
            con.close()
    
    def is_valid(self, row: dict, all_rows: list) -> bool:
        """Validate row: columns + required fields not empty + pk duplicates + barcode ranges.
        Returns True if valid, False if invalid."""
        if not self.validate_columns(row):
            return False
        
        # Check required columns are not empty
        for col in self.columns:
            if col.required:
                val = row.get(col.name)
                if val is None or str(val).strip() == "":
                    return False
        
        if self._check_primary_key_duplicates(row, all_rows):
            return False
        
        for col in self.columns:
            if type(col) == BarcodeColumn and not col.is_valid_barcode(row[col.name]):
                return False

        return True
    
    def get(self) -> pd.DataFrame:
        """Return all rows as strings."""
        query = f"SELECT * FROM {self.table_name}"
        col_names = [col.name for col in self.columns]
        return self.connection.get_query(query, col_names)
    
    def get_typed(self) -> pd.DataFrame:
        """Return all rows with correct Python types."""
        df = self.get()
        if df.empty:
            return pd.DataFrame({col.name: pd.Series([], dtype=col.pandas_dtype) 
                               for col in self.columns})
        for col in self.columns:
            df[col.name] = df[col.name].astype(col.pandas_dtype)
        return df
    
    def _fill_optional_defaults(self, row: dict) -> dict:
        """Fill missing or empty optional columns with their defaults."""
        for col in self.columns:
            if not col.required:
                val = row.get(col.name)
                if val is None or str(val).strip() == "":
                    row[col.name] = col.default
        return row
    
    def set(self, data: list | pd.DataFrame) -> tuple[str, list]:
        """Replace mode: fill optional defaults, validate, delete all, insert."""
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient="records")
        
        con, cur = self.connection.connect()
        bad_rows = []
        good_rows = []
        
        for row in data:
            self._fill_optional_defaults(row)            
            is_valid = self.is_valid(row, data)
            
            if not is_valid:
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
        
