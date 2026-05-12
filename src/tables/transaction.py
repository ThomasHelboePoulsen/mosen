from src.tables.base_table import BaseTable
from src.tables.column import Column


class TransactionTable(BaseTable):
    table_name = "transactions"
    columns = [
        Column("barcode_user", str, required=True),
        Column("barcode_prod", str, required=True),
        Column("timestamp", str, required=True),
    ]
    
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
    
    def is_valid_batch(self, row: dict, all_rows: list) -> bool:
        """Validate transaction: standard checks + product/user existence."""
        if not super().is_valid_batch(row, all_rows):
            return False
        
        if not self._validate_product_exists(row):
            return False
        
        return self._validate_user_exists(row)
    
    def _validate_product_exists(self, row: dict) -> bool:
        """Check that barcode_prod exists in products table."""
        prods = self.product_table.get()
        return str(row["barcode_prod"]) in list(prods["barcode"])
    
    def _validate_user_exists(self, row: dict) -> bool:
        """Check that barcode_user exists in users table."""
        users = self.user_table.get()
        return str(row["barcode_user"]) in list(users["barcode"])
