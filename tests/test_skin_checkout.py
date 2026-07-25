import types

import pandas as pd
import pytest
from dash import no_update

from src import trans_layout
from src.skins import checkout_theme_class, get_user_skin_key


USER_BARCODE = "1234"


def load_checkout_catalog(temp_db):
    temp_db.upload_values(
        [
            {
                "barcode": USER_BARCODE,
                "name": "U",
                "rank": "r",
                "team": "t",
                "is_guest": 0,
                "waste_cents": -1,
                "paid_cents": 0,
            }
        ],
        "users",
    )
    temp_db.upload_values(
        [
            {
                "barcode": 101,
                "name": "Soda",
                "price": 10,
                "category": "Drinks",
                "current_stock": 10,
                "initial_stock": 10,
            },
            {
                "barcode": 900,
                "name": "Deep Swamp",
                "price": 2,
                "category": "Skins",
                "current_stock": 0,
                "initial_stock": 0,
            },
            {
                "barcode": 901,
                "name": "Bog Terminal",
                "price": 2,
                "category": "Skins",
                "current_stock": 0,
                "initial_stock": 0,
            },
            {
                "barcode": 903,
                "name": "Default checkout",
                "price": 0,
                "category": "Skins",
                "current_stock": 0,
                "initial_stock": 0,
            },
        ],
        "prods",
    )


def scan(product_barcode):
    return trans_layout.new_trans(1, str(product_barcode), USER_BARCODE, [])


def temporary_barcodes(temp_db):
    return list(temp_db._temporary_table.get()["barcode_prod"])


def append_purchase(temp_db, product_barcode, index):
    result, bad_rows = temp_db._transaction_table.append(
        pd.DataFrame(
            [
                {
                    "barcode_user": USER_BARCODE,
                    "barcode_prod": product_barcode,
                    "timestamp": f"2026-01-01 10:00:0{index}",
                }
            ]
        )
    )
    assert result == "success"
    assert bad_rows == []


def open_theme(monkeypatch):
    monkeypatch.setattr(
        trans_layout,
        "ctx",
        types.SimpleNamespace(triggered_id="new_trans_inp"),
    )
    result = trans_layout.open_trans_modal(1, None, USER_BARCODE, None, [])
    assert result[0] is True
    assert result[4] is no_update
    return result[3]


def test_latest_skin_transaction_and_default_reset_determine_next_theme(
    monkeypatch,
    temp_db,
):
    load_checkout_catalog(temp_db)

    assert open_theme(monkeypatch) == checkout_theme_class("default")

    append_purchase(temp_db, 900, 0)
    assert open_theme(monkeypatch) == checkout_theme_class("swamp")

    append_purchase(temp_db, 101, 1)
    append_purchase(temp_db, 901, 2)
    assert open_theme(monkeypatch) == checkout_theme_class("retro")

    append_purchase(temp_db, 903, 3)
    assert open_theme(monkeypatch) == checkout_theme_class("default")
    assert get_user_skin_key(
        USER_BARCODE,
        temp_db._transaction_table.get(),
    ) == "default"


def test_last_scanned_skin_replaces_pending_skin_without_touching_products(temp_db):
    load_checkout_catalog(temp_db)

    assert scan(101)[2] is no_update
    assert scan(900)[2] is no_update
    assert scan(901)[2] is no_update
    result = scan(903)

    assert result[2] is no_update
    assert temporary_barcodes(temp_db) == [101, 903]
    assert [component.children for component in result[0]] == [
        "Products: ",
        "1x: Soda",
        "1x: Default checkout",
    ]


def test_skin_cannot_be_multiplied(temp_db):
    load_checkout_catalog(temp_db)
    scan(900)

    result = scan(2)

    assert result[0] is no_update
    assert result[1] == ""
    assert "cannot be multiplied" in result[2][0]["msg"]
    assert temporary_barcodes(temp_db) == [900]


def test_checkout_is_atomic_clears_cart_and_is_idempotent(temp_db):
    load_checkout_catalog(temp_db)
    temp_db.upload_values(
        [
            {"barcode_prod": 101, "name": "Soda"},
            {"barcode_prod": 900, "name": "Deep Swamp"},
        ],
        "temporary",
    )

    trans_layout.checkout_cart_to(USER_BARCODE, temp_db)
    trans_layout.checkout_cart_to(USER_BARCODE, temp_db)

    assert list(temp_db._transaction_table.get()["barcode_prod"]) == [101, 900]
    assert temp_db._temporary_table.get().empty
    assert get_user_skin_key(
        USER_BARCODE,
        temp_db._transaction_table.get(),
    ) == "swamp"


def test_clear_failure_rolls_back_transactions_and_preserves_cart(
    monkeypatch,
    temp_db,
):
    load_checkout_catalog(temp_db)
    temp_db.upload_values(
        [{"barcode_prod": 900, "name": "Deep Swamp"}],
        "temporary",
    )

    def fail_clear(_rows):
        raise RuntimeError("clear failed")

    monkeypatch.setattr(temp_db._temporary_table, "set", fail_clear)

    with pytest.raises(RuntimeError, match="clear failed"):
        trans_layout.checkout_cart_to(USER_BARCODE, temp_db)

    assert temp_db._transaction_table.get().empty
    assert temporary_barcodes(temp_db) == [900]
