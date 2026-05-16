from src.database.tables.base_table import BaseTable
from src.database.tables.column import BarcodeColumn, Column


class TemporaryTable(BaseTable):
    table_name = "temporary"
    columns = [
        BarcodeColumn("barcode_prod", int, min=100, max=999, required=True),
        Column("name", str, required=True),
    ]

    create_sql = """
        CREATE TABLE temporary (
            barcode_prod INTEGER,
            name varchar(255)
        )
    """