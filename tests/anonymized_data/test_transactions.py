import pytest
import pandas as pd
from src.data_connection import Database
from src.anonymized_data.transactions import Transactions
from src.anonymized_data.ranks import Ranks
from datetime import datetime

def test_columns_match_enum(tmp_path):
    #Arrange
    #Act
    #Assert
    assert True

def test_logical_days(tmp_path):
    #Arrange
    #Act
    #Assert
    assert True

def test_rare_combinations_masked(tmp_path):
    #Arrange
    #Act
    #Assert
    assert True

def test_aggregation(tmp_path):
    #Arrange
    success,db = create_test_db(tmp_path)
    assert success
    #Act
    ranks = Ranks(db)
    transactions = Transactions(db,ranks)
    #Assert
    assert True

def create_test_db(tmp_path):
    path = f"{tmp_path}\\test.sql"
    db = Database(path)
    success1,_ = generate_products(db)
    success2,_ = generate_users(db)
    success3,_ = generate_transactions(db)
    success = success1 and success2 and success3
    return success,db

def generate_products(db:Database):
    columns = ['barcode', 'name', 'price', 'category', 'current_stock', 'initial_stock']
    df = pd.DataFrame(data=[
        [101,"Faxe Kondi",10,"Sodavand",10,100],
        [102,"Faxe Kondi free",10,"Sodavand",10,100],
        [103,"pepsi max",1,"Sodavand",10,100],
        [104,"Grøn",10,"øl",10,100]
    ], columns=columns)
    print(df)
    upload_result,_ = db.upload_values(df,"prods")
    return upload_result=="success",df

def generate_users(db:Database):
    columns = ["barcode","name","rank","team"]
    df = pd.DataFrame(data=[
        [1001,"thomas","rus","smølfer"],
        [1002,"helboe","vektor","smølfer"],
        [1003,"poulsen","rus","smølfer"],
        [1003,"thomas2","rus","smølfer"],
    ], columns=columns)
    print(df)
    upload_result,_ = db.upload_values(df,"users")
    return upload_result=="success",df


def generate_transactions(db:Database):
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

    ], columns=columns)
    print(df)
    upload_result,_ = db.upload_values(df,"transactions")
    return upload_result=="success",df
