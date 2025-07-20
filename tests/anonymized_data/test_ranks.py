import pytest
import pandas as pd
from src.data_connection import Database
from src.anonymized_data.ranks import Ranks,EXCLUDED_STRING

MINIMUM_USER_BARCODE = 1000

def test_ranks_uniqueness(tmp_path):
    #Arrange
    rank_count = 15
    db,upload_result,_ = create_test_user_table(tmp_path,rank_count)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    assert len(ranks.included_ranks) > 1
    assert len(ranks.excluded_ranks) > 1
    assert len(set(ranks.included_ranks)) == len(ranks.included_ranks)
    shown_excluded_ranks = set(ranks.table["ranks"]).difference(set(ranks.included_ranks))
    assert len(shown_excluded_ranks) == 1
    assert shown_excluded_ranks.pop() == EXCLUDED_STRING


def test_is_included(tmp_path):
    #Arrange
    rank_count = 15
    db,upload_result,users = create_test_user_table(tmp_path,rank_count)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    assert ranks.aggregation_limit > 1
    assert ranks.aggregation_limit < rank_count
    assert set(ranks.excluded_ranks) == set([f"rank{i}" for i in range(1,ranks.aggregation_limit)])
    assert set(ranks.included_ranks) == set([f"rank{i}" for i in range(ranks.aggregation_limit,rank_count+1)])

def test_excluded_rank_names_removed(tmp_path):
    #Arrange
    rank_count = 15
    db,upload_result,_ = create_test_user_table(tmp_path,rank_count)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    assert len(ranks.excluded_ranks) > 1
    excluded_ranks_included = set(ranks.table["ranks"]).intersection(set(ranks.excluded_ranks))
    assert len(excluded_ranks_included) == 0

def test_total_user_count_consistent(tmp_path):
    #Arrange
    rank_count = 15
    db,upload_result,users = create_test_user_table(tmp_path,rank_count)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    true_user_count = len(users["barcode"])
    ranks_user_count = ranks.table["user_count"].astype(int).sum()
    assert true_user_count == ranks_user_count

def test_included_and_excluded_are_disjoint(tmp_path):
    #Arrange
    rank_count = 15
    db,upload_result,_ = create_test_user_table(tmp_path,rank_count)
    assert upload_result == "success"
    #Act
    ranks = Ranks(db)
    #Assert
    overlap = set(ranks.included_ranks
                  ).intersection(
                      set(ranks.excluded_ranks))
    assert len(overlap) == 0


def create_test_user_table(tmp_path,rank_count=15):
    users = generate_synthetic_users(rank_count)
    db = Database(f"{tmp_path}\\Test.db")
    upload_result,_ = db.upload_values(users,"users")
    return db, upload_result, users

def generate_synthetic_users(rank_count) -> pd.DataFrame:
    """generate users with distinct barcodes, where there are exactly j users in rankj. name and team don't differ"""
    columns = ["barcode","name","rank","team"]
    data = []
    user_count = 0
    for j in range(1,rank_count+1):
        data.extend([[int(1000+i+user_count),"name",f"rank{j}","team"] for i in range(j)])
        user_count += j
    users = pd.DataFrame(data,columns=columns)
    return users
