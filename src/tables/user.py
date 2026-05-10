import pandas as pd
from src.tables.base_table import BaseTable


class UserTable(BaseTable):
    table_name = "users"
    columns = {
        "barcode": int,
        "name": str,
        "rank": str,
        "team": str,
        "is_guest": int,
    }
    
    create_sql = """
        CREATE TABLE users (
            barcode varchar(255),
            name varchar(255),
            rank varchar(255),
            team varchar(255),
            is_guest INTEGER
        )
    """
    
    def validate(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Validate user: check duplicates, barcode length (4-11), find gaps if needed."""
        row, dup_bad = self._check_duplicates(row, all_rows)
        row, len_bad = self._validate_barcode_length(row, all_rows)
        bad = dup_bad or len_bad
        return row, bad
    
    def _check_duplicates(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Check for duplicate barcode in dataset and auto-increment if found."""
        bad = False
        users_df = pd.DataFrame(all_rows)
        if sum(users_df["barcode"] == row["barcode"]) > 1:
            bad = True
            row["barcode"] = max(int(b) for b in users_df["barcode"]) + 1
        return row, bad
    
    def _validate_barcode_length(self, row: dict, all_rows: list) -> tuple[dict, bool]:
        """Barcode must be 4-11 digits. Auto-fill gaps if invalid length."""
        bad = False
        if len(str(row["barcode"])) < 4 or len(str(row["barcode"])) > 11:
            bad = True
            users_df = pd.DataFrame(all_rows)
            user_barcodes = [int(b) for b in users_df["barcode"]]
            for i in range(1000, 100000000000):
                if i not in user_barcodes:
                    row["barcode"] = i
                    break
        return row, bad
