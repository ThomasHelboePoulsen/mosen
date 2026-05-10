import pandas as pd
from src.tables.base_table import BaseTable


class ProductTable(BaseTable):
    table_name = "prods"
    columns = {
        "barcode": int,
        "name": str,
        "price": float,
        "category": str,
        "current_stock": int,
        "initial_stock": int,
    }
    
    create_sql = """
        CREATE TABLE prods (
            barcode varchar(255),
            name varchar(255),
            price varchar(255),
            category varchar(255),
            current_stock varchar(255),
            initial_stock varchar(255)
        )
    """
    
    def validate(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Validate product: check columns, duplicates, barcode length, find gaps if needed."""
        row, col_bad = self._validate_columns_exist(all_rows, row)
        if col_bad:
            return row, col_bad
        
        row, dup_bad = self._check_duplicates(row, all_rows)
        row, len_bad = self._validate_barcode_length(row, all_rows)
        
        bad = dup_bad or len_bad
        return row, bad
    
    def _validate_columns_exist(self, all_rows: list, row: dict) -> tuple[dict, bool]:
        """Check that all required columns exist in dataset."""
        bad = False
        prods_df = pd.DataFrame(all_rows)
        expected_columns = ["barcode", "name", "price", "category", "current_stock", "initial_stock"]
        if set(prods_df.columns) != set(expected_columns):
            bad = True
        return row, bad
    
    def _check_duplicates(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Check for duplicate barcode in dataset and auto-increment if found."""
        bad = False
        prods_df = pd.DataFrame(all_rows)
        if sum(prods_df["barcode"] == row["barcode"]) > 1:
            bad = True
            row["barcode"] = max(int(b) for b in prods_df["barcode"]) + 1
        return row, bad
    
    def _validate_barcode_length(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Barcode must be exactly 3 digits. Auto-fill gaps if invalid length."""
        bad = False
        if len(str(row["barcode"])) != 3:
            bad = True
            prods_df = pd.DataFrame(all_rows)
            prod_barcodes = [int(b) for b in prods_df["barcode"]]
            for i in range(100, 1000):
                if i not in prod_barcodes:
                    row["barcode"] = i
                    break
        return row, bad
