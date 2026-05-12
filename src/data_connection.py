import pandas as pd
from datetime import datetime
import keyboard as k

from src.container import Container
from src.tables.product import ProductTable
from src.tables.user import UserTable
from src.tables.transaction import TransactionTable


class Database:
    """DB handler for all business objects."""
    def __init__(self, data_file="beerbase.db"):
        from src.connection import Connection
        self._connection = Connection(data_file)
        self._product_table = ProductTable(self._connection)
        self._user_table = UserTable(self._connection)
        self._transaction_table = TransactionTable(
            self._connection,
            product_table=self._product_table,
            user_table=self._user_table
        )
        self.init()
    
    def init(self):
        """Initialize connection and create all tables."""
        con, cur = self._connection.connect()
        self._create_tables()
        return con, cur
    
    def _create_tables(self):
        """Create all required tables if they don't exist."""
        table_schemas = {
            "prods": ProductTable.create_sql,
            "users": UserTable.create_sql,
            "transactions": TransactionTable.create_sql,
            "temporary": """
                CREATE TABLE temporary (
                    barcode_prod varchar(255),
                    name varchar(255)
                )
            """,
            "settings": """
                CREATE TABLE settings (
                    password varchar(255),
                    show_bill varchar(255),
                    waste varchar(255),
                    backup varchar(255)
                )
            """,
        }
        
        con, cur = self._connection.connect()
        for table_name, create_sql in table_schemas.items():
            if not self._table_exists(table_name):
                cur.execute(create_sql)
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
    
    def upload_values(self, data: list, table: str) -> tuple[str, list]:
        """Upload data to table."""
        if table == "prods":
            return self._product_table.set(data)
        elif table == "users":
            return self._user_table.set(data)
        elif table == "transactions":
            return self._transaction_table.set(data)
        else:
            raise ValueError(f"Unknown table: {table}")
    
    @property
    def data_file(self):
        return self._connection.data_file


def get_prods():
    return Container.get(Database)._product_table.get()

def get_trans():
    return Container.get(Database)._transaction_table.get()

def get_users():
    return Container.get(Database)._user_table.get()

def get_current_trans():
    query = "SELECT * FROM temporary"
    cols = ["barcode_prod", "name"]
    return Container.get(Database).get_query(query, cols)

def update_current_trans(data: pd.DataFrame):
    con, cur = Container.get(Database).init()
    if len(data.columns) == 2:
        data.to_sql(name="temporary", con=con, if_exists="replace", index=False)
        con.commit()
    else:
        raise ValueError("Incorrect data")

def reset_table(table: str):
    con, cur = Container.get(Database).init()
    cur.execute(f"DELETE FROM {table}")
    print(f"Reset on {table}")
    con.commit()

def reset_current_trans():
    reset_table("temporary")

def upload_values(data: list, table: str):
    return Container.get(Database).upload_values(data, table)

def add_transactions(trans_df):
    con, cur = Container.get(Database).init()
    trans_df.to_sql(name="transactions", con=con, if_exists="append", index=False)

def check_db(data, con, cur):
    if len(data) == 0:
        out = cur.execute("SELECT * FROM settings")
        cur.execute("INSERT INTO settings VALUES ('OLProgram', 'True', '0', '10')")
        con.commit()
        print("updated database")
        return False
    else:
        return True

def get_password():
    con, cur = Container.get(Database).init()
    data = list(cur.execute("SELECT password FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT password FROM settings"))
    return data[0][0]

def get_backup_time():
    con, cur = Container.get(Database).init()
    data = list(cur.execute("SELECT backup FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT backup FROM settings"))
    return int(data[0][0])

def get_show_bill():
    con, cur = Container.get(Database).init()
    data = list(cur.execute("SELECT show_bill FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT show_bill FROM settings"))
    return data[0][0] == "True"

def get_waste():
    con, cur = Container.get(Database).init()
    data = list(cur.execute("SELECT waste FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT waste FROM settings"))
    return int(data[0][0])

def update_values(password=None, show_bill=None, waste=None, backup_time=None):
    con, cur = Container.get(Database).init()
    inps = {
        "password": password,
        "show_bill": show_bill,
        "waste": waste,
        "backup": backup_time,
    }
    for key, value in inps.items():
        if value is None:
            continue
        cur.execute(f"""UPDATE settings SET "{key}" = '{value}'""")
        con.commit()

def reset_all_tables():
    con, cur = Container.get(Database).init()
    for table in ["users", "prods", "transactions", "temporary", "settings"]:
        cur.execute(f"DROP TABLE {table}")
        con.commit()
    db = Database()
    Container.set(Database, db)
    k.unhook_all()
    k.send("alt+f4")
