import pandas as pd
from src.tables.base_table import BaseTable
from src.tables.column import Column,BarcodeColumn


class ProductTable(BaseTable):
    table_name = "prods"
    columns = [
        BarcodeColumn("barcode", int, min=100, max=999, required=True, is_primary_key=True),
        Column("name", str, required=True),
        Column("price", float, required=True),
        Column("category", str, required=True),
        Column("current_stock", int, required=True),
        Column("initial_stock", int, required=True),
    ]
    
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
