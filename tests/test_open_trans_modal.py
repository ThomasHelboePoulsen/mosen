import types
import pandas as pd
import pytest
from dash import no_update

from src import trans_layout
from src.database.data_connection import update_values
from src.skins import checkout_theme_class


def _load_balance_graph_data(temp_db):
    temp_db.upload_values(
        [
            {"barcode": "1000", "name": "Anna", "rank": "r", "team": "t"},
            {"barcode": "1001", "name": "Bo", "rank": "r", "team": "t"},
            {"barcode": "1002", "name": "No Purchases", "rank": "r", "team": "t"},
        ],
        "users",
    )
    temp_db.upload_values(
        [
            {
                "barcode": "100",
                "name": "Beer",
                "price": 10.0,
                "category": "c",
                "current_stock": 10,
                "initial_stock": 10,
            },
            {
                "barcode": "101",
                "name": "Soda",
                "price": 5.0,
                "category": "c",
                "current_stock": 10,
                "initial_stock": 10,
            },
        ],
        "prods",
    )
    temp_db._transaction_table.append(
        pd.DataFrame(
            [
                {
                    "barcode_user": "1000",
                    "barcode_prod": "100",
                    "timestamp": "2026-01-01 10:00:00",
                },
                {
                    "barcode_user": "1000",
                    "barcode_prod": "100",
                    "timestamp": "2026-01-01 10:01:00",
                },
                {
                    "barcode_user": "1001",
                    "barcode_prod": "101",
                    "timestamp": "2026-01-01 10:02:00",
                },
            ]
        )
    )


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
    assert res[3] == checkout_theme_class(None)
    assert isinstance(res[4], list)
    assert "Invalid barcode" in res[4][0]["msg"]


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
    assert res[3] is no_update
    assert isinstance(res[4], list)
    assert "Invalid barcode" in res[4][0]["msg"]


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
    assert res[3] == checkout_theme_class(None)
    assert isinstance(res[4], list)
    assert "No users exist" in res[4][0]["msg"]


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
    assert res[3] == checkout_theme_class(None)
    assert res[4] is no_update
    assert called["reset"] is True


def test_transaction_graph_hides_index_axis_labels(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    temp_db.upload_values([
        {"barcode": "101", "name": "P", "price": 1.0, "category": "c", "current_stock": 10, "initial_stock": 10}
    ], "prods")
    temp_db._transaction_table.append(
        pd.DataFrame(
            [
                {
                    "barcode_user": "1234",
                    "barcode_prod": "101",
                    "timestamp": "2026-01-01 10:00:00",
                }
            ]
        )
    )
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")

    # Act
    fig, error = trans_layout.get_transactions(1, "1234", [])

    # Assert
    assert error is no_update
    assert fig.layout.xaxis.title.text is None
    assert fig.layout.xaxis.showticklabels is False
    assert fig.layout.yaxis.title.text == "amount"
    assert fig.layout.yaxis.dtick == 1
    assert fig.layout.paper_bgcolor == "#ffffff"
    assert fig.layout.plot_bgcolor == "#ffffff"
    assert fig.layout.legend.title.text is None


def test_transaction_graph_counts_only_selected_user(monkeypatch, temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1000")

    # Act
    fig, error = trans_layout.get_transactions(1, "1000", [])

    # Assert
    assert error is no_update
    assert [trace.name for trace in fig.data] == ["Beer"]
    assert list(fig.data[0].y) == [2]


def test_transaction_graph_empty_for_user_without_transactions(monkeypatch, temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1002")

    # Act
    fig, error = trans_layout.get_transactions(1, "1002", [])

    # Assert
    assert error is no_update
    assert len(fig.data) == 0
    assert fig.layout.xaxis.showticklabels is False
    assert fig.layout.yaxis.dtick == 1


def test_transaction_graph_unknown_user_adds_error(monkeypatch, temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "9999")

    # Act
    fig, error = trans_layout.get_transactions(1, "9999", [])

    # Assert
    assert fig is no_update
    assert isinstance(error, list)
    assert "User not found" in error[0]["msg"]


def test_show_balance_with_bill_enabled_uses_only_selected_user_transactions(temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    update_values(
        show_bill=True,
        waste_cents=0,
        bill_preview_waste_extra_percent=0,
    )

    # Act
    result = trans_layout.show_balance(1, "1000")

    # Assert
    assert result == "Anna - Current bill is approximately: 20"


def test_show_balance_with_bill_disabled_returns_only_user_name(temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    update_values(show_bill=False)

    # Act
    result = trans_layout.show_balance(1, "1000")

    # Assert
    assert result == "Anna"


def test_show_balance_unknown_user_returns_no_update(temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    update_values(show_bill=True)

    # Act
    result = trans_layout.show_balance(1, "9999")

    # Assert
    assert result is no_update


def test_show_balance_includes_waste_preview(temp_db):
    # Arrange
    _load_balance_graph_data(temp_db)
    update_values(
        show_bill=True,
        waste_cents=300,
        bill_preview_waste_extra_percent=0,
    )

    # Act
    result = trans_layout.show_balance(1, "1000")

    # Assert
    assert result == "Anna - Current bill is approximately: 21"


def test_paid_user_cannot_open_transaction_modal(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([
        {
            "barcode": "1234",
            "name": "U",
            "rank": "r",
            "team": "t",
            "is_guest": 0,
            "paid_cents": 100,
        }
    ], "users")
    monkeypatch.setattr(trans_layout, "get_barcode", lambda v: "1234")
    monkeypatch.setattr(trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp"))

    # Act
    res = trans_layout.open_trans_modal(1, None, "1234", None, [])

    # Assert
    assert res[0] is no_update
    assert res[1] == ""
    assert res[2] is no_update
    assert res[3] == checkout_theme_class(None)
    assert isinstance(res[4], list)
    assert "already paid" in res[4][0]["msg"]


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

    # Act
    res = trans_layout.open_trans_modal(None, 1, "123", "123", [])

    # Assert
    assert res[0] is False
    assert res[1] == ""
    assert res[2] is no_update
    assert res[3] is no_update
    assert res[4] is no_update
    assert len(temp_db._transaction_table.get()) == 1
    assert temp_db._temporary_table.get().empty


def test_duplicate_checkout_only_adds_basket_once(temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    temp_db.upload_values([
        {"barcode": "101", "name": "P", "price": 1.0, "category": "c", "current_stock": 10, "initial_stock": 10}
    ], "prods")
    temp_db.upload_values([
        {"barcode_prod": "101", "name": "P"}
    ], "temporary")

    # Act
    trans_layout.checkout_cart_to("1234", temp_db)
    trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    transactions = temp_db._transaction_table.get()
    assert len(transactions) == 1
    assert transactions.iloc[0]["barcode_user"] == 1234
    assert transactions.iloc[0]["barcode_prod"] == 101
    assert temp_db._temporary_table.get().empty


def test_empty_checkout_is_harmless(temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")

    # Act
    trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert temp_db._transaction_table.get().empty
    assert temp_db._temporary_table.get().empty


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
    assert res[3] == checkout_theme_class(None)
    assert isinstance(res[4], list)
    assert "Empty barcode" in res[4][0]["msg"]


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

    # Make append report failure after writing, so the outer transaction must roll it back.
    original_append = temp_db._transaction_table.append

    def fake_append(df):
        result, bad_rows = original_append(df)
        assert result == "success"
        assert bad_rows == []
        return "failed", [{"row": 1}]

    monkeypatch.setattr(temp_db._transaction_table, "append", fake_append)

    # Act
    res = trans_layout.open_trans_modal(None, 1, "123", "123", [])

    # Assert
    assert res[0] is no_update
    assert res[1] is no_update
    assert res[2] is no_update
    assert res[3] is no_update
    assert isinstance(res[4], list)
    assert "Failed to add transactions" in res[4][0]["msg"]
    assert temp_db._transaction_table.get().empty
    current = temp_db._temporary_table.get()
    assert len(current) == 1
    assert current.iloc[0]["barcode_prod"] == 101


def test_clear_failure_rolls_back_appended_transactions(monkeypatch, temp_db):
    # Arrange
    temp_db.upload_values([
        {"barcode": "1234", "name": "U", "rank": "r", "team": "t", "is_guest": 0}
    ], "users")
    temp_db.upload_values([
        {"barcode": "101", "name": "P", "price": 1.0, "category": "c", "current_stock": 10, "initial_stock": 10}
    ], "prods")
    temp_db.upload_values([
        {"barcode_prod": "101", "name": "P"}
    ], "temporary")

    def fail_clear(_rows):
        raise RuntimeError("clear failed")

    monkeypatch.setattr(temp_db._temporary_table, "set", fail_clear)

    # Act
    with pytest.raises(RuntimeError, match="clear failed"):
        trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert temp_db._transaction_table.get().empty
    current = temp_db._temporary_table.get()
    assert len(current) == 1
    assert current.iloc[0]["barcode_prod"] == 101


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
    assert res[4] is no_update
