import pytest
import pandas as pd
from src.data_connection import Database
from src.container import Container
from src.anonymized_data.transactions import Transactions,Cols,PRODUCT_SANITIEZED_STR
from src.anonymized_data.ranks import Ranks


def test_valid_returned_table(tmp_path):
    #Arrange
    success,db = create_test_db(tmp_path)
    assert success
    #Act
    ranks = Ranks(db,aggregation_limit=1)
    transactions = Transactions(db,ranks)
    #Assert
    columns = [str(col) for col in [Cols.RANK,Cols.LOGICAL_DAY,Cols.WEEKDAY_NAME,Cols.BARCODE_PROD,Cols.AMOUNT]]
    expected_data = [
        ["rus","2003-03-03","Monday",str(101),8],
        ["rus","2003-03-04","Tuesday",PRODUCT_SANITIEZED_STR,5],
        ["vektor","2003-03-03","Monday",PRODUCT_SANITIEZED_STR,1],
    ]
    expected_table = pd.DataFrame(expected_data,columns=columns)
    expected_table[Cols.AMOUNT] = expected_table[Cols.AMOUNT].astype(int)
    assert transactions.table.equals(expected_table)

def create_test_db(tmp_path):
    path = f"{tmp_path}\\test.sql"
    db = Database(path)
    db.init()
    Container.set_db(db)
    success1,_ = generate_products()
    success2,_ = generate_users()
    success3,_ = generate_transactions()
    success = success1 and success2 and success3
    return success, db._connection

def generate_products():
    from src.tables.product import ProductTable
    from src.container import Container
    columns = ['barcode', 'name', 'price', 'category', 'current_stock', 'initial_stock']
    df = pd.DataFrame(data=[
        [101,"Faxe Kondi",10,"Sodavand",10,100],
        [102,"Faxe Kondi free",10,"Sodavand",10,100],
        [103,"pepsi max",1,"Sodavand",10,100],
        [104,"Grøn",10,"øl",10,100]
    ], columns=columns)
    upload_result,_ = ProductTable(Container.get_db()._connection).set(df)
    return upload_result=="success",df

def generate_users():
    from src.tables.user import UserTable
    from src.container import Container
    columns = ["barcode","name","rank","team"]
    df = pd.DataFrame(data=[
        [1001,"thomas","rus","smølfer"],
        [1002,"helboe","vektor","smølfer"],
        [1003,"poulsen","rus","smølfer"],
        [1004,"thomas2","rus","smølfer"],
    ], columns=columns)
    upload_result,_ = UserTable(Container.get_db()._connection).set(df)
    return upload_result=="success",df


def generate_transactions():
    from src.tables.transaction import TransactionTable
    from src.container import Container
    columns = ['barcode_user', 'barcode_prod', 'timestamp']
    day1 = "03/03/2003"
    day2 = "04/03/2003"
    df = pd.DataFrame(data=[
        [1001,101,f"{day1} 20:00:00"],
        [1002,101,f"{day1} 21:00:00"],
        [1003,101,f"{day1} 22:00:00"],
        [1004,101,f"{day1} 23:00:00"],
        [1001,101,f"{day1} 23:59:00"],
        [1001,101,f"{day2} 01:00:00"],
        [1001,101,f"{day2} 02:00:00"],
        [1001,101,f"{day2} 03:00:00"],
        [1001,101,f"{day2} 04:00:00"],
        [1001,101,f"{day2} 05:01:00"], #logical day2 start
        [1001,101,f"{day2} 06:00:00"],
        [1001,101,f"{day2} 07:00:00"],
        [1001,101,f"{day2} 08:00:00"],
        [1001,101,f"{day2} 08:00:00"],

    ], columns=columns)
    db = Container.get_db()
    upload_result,_ = TransactionTable(
        db._connection,
        product_table=db._product_table,
        user_table=db._user_table
    ).set(df)
    return upload_result=="success",df
