from src.database.tables.base_table import BaseTable
from src.database.tables.column import Column


class TemporaryTable(BaseTable):
    table_name = "temporary"
    columns = [
        Column("barcode_prod", str, required=True),
        Column("name", str, required=True),
    ]

    create_sql = """
        CREATE TABLE temporary (
            barcode_prod varchar(255),
            name varchar(255)
        )
    """