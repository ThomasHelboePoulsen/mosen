import types
import pandas as pd
from dash import no_update

from src import trans_layout


def test_bad_barcode_open(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "bad barcode")
    # no users in DB
    temp_db.upload_values([], "users")

    # Act
    res = trans_layout.open_trans_modal(None, None, "xxx", "yyy", [])

    # Assert
    assert res[0] is no_update
    assert res[1] == ""
    assert res[2] is no_update
    assert isinstance(res[3], list)
    assert "Invalid barcode" in res[3][0]["msg"]


def test_bad_barcode_close(monkeypatch, temp_db):
    def fake_get_barcode(v):
        return "bad barcode" if v == "close" else "1234"
    # Arrange
    monkeypatch.setattr(trans_layout, "get_barcode", fake_get_barcode)
    # no users in DB
    temp_db.upload_values([], "users")

    # Act
    res = trans_layout.open_trans_modal(None, None, "ok", "close", [])

    # Assert
    assert res[0] is no_update
    assert res[1] is no_update
    assert res[2] == ""
    assert isinstance(res[3], list)
    assert "Invalid barcode" in res[3][0]["msg"]


def test_no_users_exists(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([], "users")
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp"))

    # Act
    res = trans_layout.open_trans_modal(1, None, "1234", None, [])

    # Assert
    assert res[0] is no_update
    assert res[1] == ""
    assert res[2] is no_update
    assert isinstance(res[3], list)
    assert "No users exist" in res[3][0]["msg"]


def test_new_trans_inp_success(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp"))

    called = {"reset": False}

    def fake_reset():
        called["reset"] = True

    monkeypatch.setattr(trans_layout, "reset_current_trans", fake_reset)

    # Act
    res = trans_layout.open_trans_modal(1, None, "123", None, [])

    # Assert
    assert res[0] is True
    assert res[1] is no_update
    assert res[2] == ""
    assert res[3] is no_update
    assert called["reset"] is True


def test_prod_barcode_success(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    temp_db.upload_values([
        {"barcode": "101", "name": "P", "price": 1.0, "category": "c", "current_stock": 10, "initial_stock": 10}
    ], "prods")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="prod_barcode"))
    temp_db.upload_values([
        {"barcode_prod": "101", "name": "P"}
    ], "temporary")

    def fake_add(rows):
        return "success", []

    monkeypatch.setattr(trans_layout, "add_transactions", fake_add)

    # Act
    res = trans_layout.open_trans_modal(None, 1, "123", "123", [])

    # Assert
    assert res[0] is False
    assert res[1] == ""
    assert res[2] is no_update
    assert res[3] is no_update


def test_empty_barcode_open(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: None)
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp"))

    # Act
    res = trans_layout.open_trans_modal(1, None, None, None, [])

    # Assert
    assert res[0] is no_update
    assert res[1] == ""
    assert res[2] is no_update
    assert isinstance(res[3], list)
    assert "Empty barcode" in res[3][0]["msg"]


def test_add_transactions_failure(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    temp_db.upload_values([
        {"barcode": "101", "name": "P", "price": 1.0, "category": "c", "current_stock": 10, "initial_stock": 10}
    ], "prods")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="prod_barcode"))
    temp_db.upload_values([
        {"barcode_prod": "101", "name": "P"}
    ], "temporary")

    # Make add_transactions fail by monkeypatching the table append directly
    original_append = temp_db._transaction_table.append

    def fake_append(df):
        return "failed", [{"row": 1}]

    monkeypatch.setattr(temp_db._transaction_table, "append", fake_append)

    # Act
    res = trans_layout.open_trans_modal(None, 1, "123", "123", [])

    # Assert
    assert res[0] is no_update
    assert res[1] is no_update
    assert res[2] is no_update
    assert isinstance(res[3], list)
    assert "Failed to add transactions" in res[3][0]["msg"]


def test_unexpected_error_branch(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="some_other"))

    # Act
    res = trans_layout.open_trans_modal(None, None, "123", "123", [])

    # Assert
    assert res[0] is no_update
    assert res[1] is no_update
    assert res[2] is no_update
    assert res[3] is no_update
