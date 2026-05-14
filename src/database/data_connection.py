import pandas as pd
from datetime import datetime
import keyboard as k

from src.container import Container
from src.database.tables.base_table import BaseTable
from src.database.tables.product import ProductTable
from src.database.tables.settings import SettingsTable
from src.database.tables.temporary import TemporaryTable
from src.database.tables.user import UserTable
from src.database.tables.transaction import TransactionTable


#TODO: schedule cache refreshes and report if they were stale.

class Database:
    """DB handler for all business objects."""
    def __init__(self, data_file="beerbase.db"):
        from src.database.connection import Connection
        self._connection = Connection(data_file)
        self._product_table = ProductTable(self._connection)
        self._user_table = UserTable(self._connection)
        self._transaction_table = TransactionTable(
            self._connection,
            product_table=self._product_table,
            user_table=self._user_table
        )
        self._temporary_table = TemporaryTable(self._connection)
        self._settings_table = SettingsTable(self._connection)
        self.tables = {
            self._product_table.table_name: self._product_table,
            self._user_table.table_name: self._user_table,
            self._transaction_table.table_name: self._transaction_table,
            self._temporary_table.table_name: self._temporary_table,
            self._settings_table.table_name: self._settings_table,
        }
        self.init()
    
    def init(self):
        """Initialize connection and create all tables."""
        con, cur = self._connection.connect()
        self._create_tables()
        self._settings_table.ensure_defaults()
        return con, cur
    
    def _create_tables(self):
        """Create all required tables if they don't exist."""
        con, cur = self._connection.connect()
        for table_name, table in self.tables.items():
            if not self._table_exists(table_name):
                cur.execute(table.create_sql)
                con.commit()
        con.close()
    
    def _table_exists(self, table_name: str) -> bool:
        return self._connection.table_exists(table_name)
    
    def get_query(self, query: str, columns: list):
        return self._connection.get_query(query, columns)
    
    def validate_prod(self, row: dict, data: list) -> bool:
        """Validate product (batch mode: data includes row being tested)."""
        return self._product_table.is_valid_batch(row, data)
    
    def validate_user(self, row: dict, data: list) -> bool:
        """Validate user (batch mode: data includes row being tested)."""
        return self._user_table.is_valid_batch(row, data)
    
    def validate_trans(self, row: dict, data: list) -> bool:
        """Validate transaction (batch mode: data includes row being tested)."""
        return self._transaction_table.is_valid_batch(row, data)
    
    def get_table(self,table_name: str) -> BaseTable:
        if table_name not in self.tables:
            raise ValueError(f"Unknown table: {table_name}")
        return self.tables[table_name]
    
    def upload_values(self, data: list, table: str) -> tuple[str, list]:
        """Upload data to table."""
        return self.get_table(table).set(data)

    @property
    def prods(self):
        return self._product_table.get()

    @property
    def users(self):
        return self._user_table.get()

    @property
    def transactions(self):
        return self._transaction_table.get()

    @property
    def temporary(self):
        return self._temporary_table.get()

    @property
    def settings(self):
        return self._settings_table.get()
    
    @property
    def data_file(self):
        return self._connection.data_file


def get_prods():
    return Container.get(Database).prods

def get_trans():
    return Container.get(Database).transactions

def get_users():
    return Container.get(Database).users

def get_current_trans():
    return Container.get(Database).temporary

def update_current_trans(data: pd.DataFrame):
    if len(data.columns) == 2:
        Container.get(Database)._temporary_table.set(data)
    else:
        raise ValueError("Incorrect data")

def reset_table(table: str):
    db = Container.get(Database)
    if table not in db.tables:
        raise ValueError(f"Unknown table: {table}")
    db.get_table(table).set([])
    print(f"Reset on {table}")

def reset_current_trans():
    reset_table("temporary")

def upload_values(data: list, table: str):
    return Container.get(Database).upload_values(data, table)

def add_transactions(trans_df):
    return Container.get(Database)._transaction_table.append(trans_df)

def get_password():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return str(db.settings.iloc[0]["password"])

def get_backup_time():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["backup"])

def get_show_bill():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return db.settings.iloc[0]["show_bill"] == "True"

def get_waste():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["waste"])

def update_values(password=None, show_bill=None, waste=None, backup_time=None):
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    settings_row = db.settings.iloc[0].to_dict()
    inps = {
        "password": password,
        "show_bill": show_bill,
        "waste": waste,
        "backup": backup_time,
    }
    for key, value in inps.items():
        if value is None:
            continue
        settings_row[key] = str(value)
    db._settings_table.set([settings_row])

def reset_all_tables():
    con, cur = Container.get(Database).init()
    for table in ["users", "prods", "transactions", "temporary", "settings"]:
        cur.execute(f"DROP TABLE {table}")
        con.commit()
    Container.set(Database, Database())
    k.unhook_all()
    k.send("alt+f4")
