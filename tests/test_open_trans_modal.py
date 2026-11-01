import types
from threading import Barrier, Thread

import pandas as pd
import pytest
from dash import no_update

from src import trans_layout
from src.database.data_connection import update_values


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


def _load_checkout_data(temp_db, product_count=1):
    temp_db.upload_values(
        [
            {
                "barcode": "1234",
                "name": "U",
                "rank": "r",
                "team": "t",
                "is_guest": 0,
            }
        ],
        "users",
    )
    temp_db.upload_values(
        [
            {
                "barcode": "101",
                "name": "P",
                "price": 1.0,
                "category": "c",
                "current_stock": 10,
                "initial_stock": 10,
            }
        ],
        "prods",
    )
    temp_db.upload_values(
        [
            {
                "barcode_prod": "101",
                "name": "P",
            }
            for _ in range(product_count)
        ],
        "temporary",
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
    assert isinstance(res[-1], list)
    assert res[-1][0]["msg"] == "Invalid barcode: 'xxx'"


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
    assert isinstance(res[-1], list)
    assert res[-1][0]["msg"] == "Invalid barcode: 'close'"


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
    assert isinstance(res[-1], list)
    assert "No users exist" in res[-1][0]["msg"]


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
    assert [line.children for line in res[3]] == ["Products: "]
    assert res[-1] is no_update
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
    assert error[0]["msg"] == "User not found: 9999"


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
    assert isinstance(res[-1], list)
    assert res[-1][0]["msg"] == "User has already paid: 1234"


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
    assert res[-1] is no_update


def test_checkout_records_basket_once_and_clears_temporary_table(temp_db):
    # Arrange
    _load_checkout_data(temp_db, product_count=2)

    # Act
    trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert len(temp_db.transactions) == 2
    assert temp_db.temporary.empty


def test_repeated_checkout_is_a_successful_no_op(temp_db):
    # Arrange
    _load_checkout_data(temp_db, product_count=2)

    # Act
    trans_layout.checkout_cart_to("1234", temp_db)
    trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert len(temp_db.transactions) == 2
    assert temp_db.temporary.empty


def test_empty_checkout_is_a_successful_no_op(temp_db):
    # Arrange
    _load_checkout_data(temp_db, product_count=0)

    # Act
    trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert temp_db.transactions.empty
    assert temp_db.temporary.empty


def test_concurrent_checkout_consumes_basket_only_once(temp_db):
    # Arrange
    _load_checkout_data(temp_db, product_count=2)
    start = Barrier(3)
    errors = []

    def checkout():
        start.wait()
        try:
            trans_layout.checkout_cart_to("1234", temp_db)
        except Exception as error:
            errors.append(error)

    threads = [Thread(target=checkout) for _ in range(2)]
    for thread in threads:
        thread.start()

    # Act
    start.wait()
    for thread in threads:
        thread.join()

    # Assert
    assert errors == []
    assert len(temp_db.transactions) == 2
    assert temp_db.temporary.empty


def test_checkout_append_failure_preserves_temporary_basket(monkeypatch, temp_db):
    # Arrange
    _load_checkout_data(temp_db)
    monkeypatch.setattr(
        temp_db._transaction_table,
        "append",
        lambda _rows: ("failed", [{"row": 1}]),
    )

    # Act
    with pytest.raises(ValueError, match="Failed to add transactions"):
        trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert temp_db.transactions.empty
    assert len(temp_db.temporary) == 1


def test_checkout_clear_failure_rolls_back_purchase_and_preserves_basket(
    monkeypatch,
    temp_db,
):
    # Arrange
    _load_checkout_data(temp_db)

    def fail_to_clear(_rows):
        raise RuntimeError("temporary clear failed")

    monkeypatch.setattr(temp_db._temporary_table, "set", fail_to_clear)

    # Act
    with pytest.raises(RuntimeError, match="temporary clear failed"):
        trans_layout.checkout_cart_to("1234", temp_db)

    # Assert
    assert temp_db.transactions.empty
    assert len(temp_db.temporary) == 1


def test_checkout_scan_keeps_visible_basket(temp_db):
    _load_checkout_data(temp_db, product_count=2)

    result = trans_layout.new_trans(1, True, "001234", "1234", [])

    assert result == (no_update, "", no_update)
    assert len(temp_db.temporary) == 2


def test_opening_returns_fresh_basket(monkeypatch, temp_db):
    _load_checkout_data(temp_db, product_count=2)
    monkeypatch.setattr(
        trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp")
    )

    result = trans_layout.open_trans_modal(1, None, "1234", "101", [])

    assert result[0] is True
    assert [line.children for line in result[3]] == ["Products: "]
    assert result[-1] is no_update
    assert temp_db.temporary.empty


def test_failed_opening_keeps_basket(monkeypatch, temp_db):
    _load_checkout_data(temp_db, product_count=2)
    monkeypatch.setattr(
        trans_layout, "ctx", types.SimpleNamespace(triggered_id="new_trans_inp")
    )

    def fail():
        raise RuntimeError("reset failed")

    monkeypatch.setattr(trans_layout, "reset_current_trans", fail)

    result = trans_layout.open_trans_modal(1, None, "1234", None, [])

    assert result[:4] == (no_update,) * 4
    assert result[-1][0]["msg"] == "reset failed"
    assert len(temp_db.temporary) == 2


def test_scans_multipliers_and_removal_update_display(temp_db):
    _load_checkout_data(temp_db, product_count=0)

    added = trans_layout.new_trans(1, True, "101", "1234", [])
    multiplied = trans_layout.new_trans(2, True, "3", "1234", [])
    removed = trans_layout.new_trans(3, True, "0", "1234", [])

    assert [line.children for line in added[0]] == ["Products: ", "1x: P"]
    assert [line.children for line in multiplied[0]] == ["Products: ", "3x: P"]
    assert [line.children for line in removed[0]] == ["Products: "]
    assert all(result[1:] == ("", no_update) for result in [added, multiplied, removed])
    assert temp_db.temporary.empty


def test_basket_display_counts_products_in_scan_order():
    basket = pd.DataFrame([
        {"barcode_prod": "102", "name": "Soda"},
        {"barcode_prod": "101", "name": "Beer"},
        {"barcode_prod": "102", "name": "Soda"},
    ])

    display = trans_layout._render_basket(basket)

    assert [line.children for line in display] == ["Products: ", "2x: Soda", "1x: Beer"]


def test_scan_after_closing_is_ignored(temp_db):
    result = trans_layout.new_trans(1, False, "1234", "", [])

    assert result == (no_update, no_update, no_update)


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
    assert isinstance(res[-1], list)
    assert "Empty barcode" in res[-1][0]["msg"]


@pytest.mark.parametrize("table, method", [("transactions", "append"), ("temporary", "set")])
def test_checkout_failure_keeps_basket_and_allows_retry(monkeypatch, temp_db, table, method):
    _load_checkout_data(temp_db, product_count=2)
    basket_before = temp_db.temporary
    monkeypatch.setattr(
        trans_layout, "ctx", types.SimpleNamespace(triggered_id="prod_barcode")
    )

    def fail(_rows):
        raise RuntimeError("checkout failed")

    with monkeypatch.context() as failure:
        failure.setattr(temp_db.get_table(table), method, fail)
        result = trans_layout.open_trans_modal(None, 1, "1234", "1234", [])

    assert result[:4] == (no_update,) * 4
    assert result[-1][0]["msg"] == "checkout failed"
    assert temp_db.temporary.equals(basket_before)
    assert temp_db.transactions.empty
    assert trans_layout.new_trans(1, True, "1234", "1234", []) == (no_update, "", no_update)

    retry = trans_layout.open_trans_modal(None, 2, "1234", "1234", [])

    assert retry[:4] == (False, "", no_update, no_update)
    assert retry[-1] is no_update
    assert temp_db.temporary.empty
    assert len(temp_db.transactions) == 2


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
    assert res[-1] is no_update
