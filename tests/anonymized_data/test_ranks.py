import pytest
import pandas as pd
from src.data_connection import Database
from src.anonymized_data.ranks import Ranks

MINIMUM_USER_BARCODE = 1000
#TODO: implement tests

def test_all_ranks_unique(tmp_path):

    assert True

def test_is_included(tmp_path):
    #Arrange
    db,upload_result,rank_count = create_test_user_table(tmp_path)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    assert set(ranks.excluded_ranks) == set([f"rank{i}" for i in range(1,9+1)])
    assert set(ranks.included_ranks) == set([f"rank{i}" for i in range(10,rank_count+1)])

def test_excluded_rank_names_removed():
    assert True

def test_total_user_count_consistent():
    assert True

def test_included_and_excluded_are_disjoint():
    assert True

def create_test_user_table(tmp_path):
    columns = ["barcode","name","rank","team"]
    data = []
    rank_count = 15
    user_count = 0
    for j in range(1,rank_count+1):
        data.extend([[int(1000+i+user_count),"name",f"rank{j}","team"] for i in range(j)])
        user_count += j
    users = pd.DataFrame(data,columns=columns)
    db = Database(f"{tmp_path}\\Test.db")
    upload_result,_ = db.upload_values(users,"users")
    return db, upload_result,rank_count
