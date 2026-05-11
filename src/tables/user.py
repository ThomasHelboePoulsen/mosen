from src.tables.base_table import BaseTable
from src.tables.column import Column,BarcodeColumn


class UserTable(BaseTable):
    table_name = "users"
    columns = [
        BarcodeColumn("barcode", int, min=1000, max=99999999999, required=True, is_primary_key=True),
        Column("name", str, required=True),
        Column("rank", str, required=True),
        Column("team", str, required=True),
        Column("is_guest", int, required=False, default=0),
    ]
    
    create_sql = """
        CREATE TABLE users (
            barcode varchar(255),
            name varchar(255),
            rank varchar(255),
            team varchar(255),
            is_guest INTEGER
        )
    """
    