import pandas as pd
import pytest
import types

from src.analytics.product_calculations import get_waste_table
from src.analytics.trans_calculations import (
    get_income,
    get_preview_user_waste_cents,
)
from src.analytics.waste_allocation import allocate_waste, get_strategy_options
from src.container import Container
from src.database.data_connection import (
    Database,
    add_transactions,
    get_waste_cents,
    update_values,
    upload_values,
)
from src.tables.prod_callbacks import confirm_new_stock
from src.tables.user_callbacks import add_row
from src import main_page_callbacks
from src import main_layout


@pytest.fixture
def test_db(tmp_path):
    db = Database(str(tmp_path / "waste.db"))
    Container.set(Database, db)
    yield db
    Container.reset()


def add_users(users):
    upload_values(pd.DataFrame(users), "users")


def add_product(current_stock=7):
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 2.5,
                    "category": "Beverage",
                    "current_stock": current_stock,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )


def add_sales(barcodes):
    if not barcodes:
        return
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": barcode,
                    "barcode_prod": 123,
                    "timestamp": f"2026-01-01 10:00:0{index}",
                }
                for index, barcode in enumerate(barcodes)
            ]
        )
    )


def test_equal_active_includes_guests_and_rounds_up(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 1},
            {"barcode": 1002, "name": "C", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000, 1001])

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 250
    assert users.loc[1000, "waste_cents"] == 200
    assert users.loc[1001, "waste_cents"] == 200
    assert users.loc[1002, "waste_cents"] == 0


def test_equal_active_falls_back_to_equal_all(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()

    allocate_waste(test_db)

    assert get_waste_cents() == 750
    assert test_db._user_table.get()["waste_cents"].tolist() == [400, 400]


def test_settlement_with_no_users_still_stores_raw_waste(test_db):
    add_product()

    allocate_waste(test_db)

    assert get_waste_cents() == 750
    assert len(test_db._user_table.get()) == 0


def test_negative_calculated_waste_is_clamped_to_zero(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product(current_stock=10)
    add_sales([1000])

    allocate_waste(test_db)

    assert get_waste_cents() == 0
    assert test_db._user_table.get().iloc[0]["waste_cents"] == 0


def test_equal_all_charges_users_without_purchases(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000])
    update_values(waste_strategy="equal_all")

    allocate_waste(test_db)

    assert test_db._user_table.get()["waste_cents"].tolist() == [300, 300]


def test_strategy_change_does_not_recalculate(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    allocate_waste(test_db)
    before = test_db._user_table.get()["waste_cents"].tolist()

    update_values(waste_strategy="equal_all")

    assert test_db._user_table.get()["waste_cents"].tolist() == before


def test_stock_confirmation_replaces_allocations(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product(current_stock=9)
    allocate_waste(test_db)
    assert test_db._user_table.get().iloc[0]["waste_cents"] == 300

    confirm_new_stock([7])

    assert test_db._user_table.get().iloc[0]["waste_cents"] == 800
    assert get_waste_cents() == 750


def test_new_user_uses_preview_fallback_and_edit_preserves_waste(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 600,
            }
        ]
    )
    update_values(waste_cents=600)
    add_row(1, [1001, "B", "R", "T", 0], None)
    users = test_db._user_table.get()
    new_user = users[users["barcode"] == 1001].iloc[0]
    assert new_user["waste_cents"] == -1
    assert get_preview_user_waste_cents(new_user, 600, len(users)) == 300

    add_row(1, [2000, "A", "R", "T", 0], 1000)
    edited = test_db._user_table.get()
    edited = edited[edited["barcode"] == 2000].iloc[0]
    assert edited["waste_cents"] == 600


def test_admin_income_does_not_use_preview_fallback(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": -1,
            }
        ]
    )
    update_values(waste_cents=600)

    income = get_income()[0]

    assert income["waste"] is None
    assert income["price"] == income["purchases"]


def test_strategy_options_are_generated_from_registry():
    assert get_strategy_options() == [
        {"label": "Equal active users", "value": "equal_active"},
        {"label": "Equal all users", "value": "equal_all"},
    ]


def test_product_waste_table_remains_live(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    before = get_waste_table()

    add_sales([1000])

    after = get_waste_table()
    assert before[0]["Waste"] == 3
    assert after[0]["Waste"] == 2


def test_payment_export_persists_fresh_allocations(test_db, monkeypatch):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000])
    update_values(waste_strategy="equal_all")
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, "Up", 0, []
    )

    assert result[0] is False
    assert test_db._user_table.get()["waste_cents"].tolist() == [300, 300]


def test_payment_confirmation_refreshes_economy_layout(monkeypatch):
    monkeypatch.setattr(main_layout.time, "sleep", lambda _: None)
    marker = object()
    monkeypatch.setattr(main_layout, "user_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "product_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "transaction_settings_layout", lambda: marker)

    result = main_layout.update_settings_layout(None, None, None, None, None, 1)

    assert result == (marker, marker, marker)
