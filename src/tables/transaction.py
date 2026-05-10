import pandas as pd
from src.tables.base_table import BaseTable


class TransactionTable(BaseTable):
    table_name = "transactions"
    columns = {
        "barcode_user": str,
        "barcode_prod": str,
        "timestamp": str,
    }
    
    create_sql = """
        CREATE TABLE transactions (
            barcode_user varchar(255),
            barcode_prod varchar(255),
            timestamp varchar(255)
        )
    """
    
    def __init__(self, connection: "Connection", product_table: "ProductTable", user_table: "UserTable"):
        self.product_table = product_table
        self.user_table = user_table
        super().__init__(connection)
    
    def validate(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Validate transaction: check that product and user barcodes exist."""
        row, prod_bad = self._validate_product_exists(row)
        row, user_bad = self._validate_user_exists(row)
        bad = prod_bad or user_bad
        return row, bad
    
    def _validate_product_exists(self, row: dict) -> tuple[dict, bool]:
        """Check that barcode_prod exists in products table."""
        bad = False
        prods = self.product_table.get()
        
        if str(row["barcode_prod"]) not in list(prods["barcode"]):
            bad = True
        return row, bad
    
    def _validate_user_exists(self, row: dict) -> tuple[dict, bool]:
        """Check that barcode_user exists in users table."""
        bad = False
        users = self.user_table.get()
        
        if str(row["barcode_user"]) not in list(users["barcode"]):
            bad = True
        return row, bad
