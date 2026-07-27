import base64
import copy
import sqlite3
import types

import pytest
from dash import no_update

from src import main_layout, main_page_callbacks
from src.analytics.product_calculations import get_waste_table
from src.analytics.trans_calculations import get_income, get_revenue
from src.database.data_connection import Database, get_last_stock_update_at, update_values
from src.container import Container


def _encoded_csv(csv):
    return "data:text/csv;base64," + base64.b64encode(
        csv.encode("utf-8")
    ).decode("ascii")


def _find_component(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]

    for child in children:
        found = _find_component(child, component_id)
        if found is not None:
            return found
    return None


def _load_transaction_data(temp_db, transactions=None):
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Alice",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    temp_db.upload_values(
        [
            {
                "barcode": "101",
                "name": "Beer",
                "price": 10,
                "category": "Drinks",
                "current_stock": 8,
                "initial_stock": 10,
            }
        ],
        "prods",
    )
    temp_db.upload_values(
        transactions
        or [
            {
                "barcode_user": "1000",
                "barcode_prod": "101",
                "timestamp": "26/07/2026 10:00:00",
            }
        ],
        "transactions",
    )


def test_income_lookup_empty_query_returns_all_rows_without_mutating_source():
    # Arrange
    rows = [
        {"barcode": "1000", "name": "Alice", "price": 12.5},
        {"barcode": "1001", "name": "Bob", "price": 8},
    ]
    original_rows = copy.deepcopy(rows)

    # Act
    result = main_page_callbacks.filter_income_rows(rows, "  ")

    # Assert
    assert result == rows
    assert result is not rows
    assert all(
        result_row is not source_row
        for result_row, source_row in zip(result, rows)
    )
    assert rows == original_rows


def test_income_lookup_matches_partial_names_case_insensitively():
    # Arrange
    rows = [
        {"barcode": "1000", "name": "Alice Jensen", "price": 12.5},
        {"barcode": "1001", "name": "ALICE Nielsen", "price": 8},
        {"barcode": "1002", "name": "Bob", "price": 4},
    ]

    # Act
    result = main_page_callbacks.filter_income_rows(rows, "alice")

    # Assert
    assert [row["barcode"] for row in result] == ["1000", "1001"]


def test_income_lookup_uses_prefix_until_barcode_is_exact():
    # Arrange
    rows = [
        {"barcode": "100", "name": "Alice", "price": 12.5},
        {"barcode": "1000", "name": "Bob", "price": 8},
        {"barcode": "2000", "name": "Carol", "price": 4},
    ]

    # Act
    partial_result = main_page_callbacks.filter_income_rows(rows, "10")
    exact_result = main_page_callbacks.filter_income_rows(rows, "100")

    # Assert
    assert [row["barcode"] for row in partial_result] == ["100", "1000"]
    assert exact_result == [{"barcode": "100", "name": "Alice", "price": 12.5}]


def test_income_lookup_callback_preserves_payment_values_and_tooltips():
    # Arrange
    rows = [
        {
            "barcode": "1000",
            "name": "Alice",
            "purchases": 10,
            "waste": 2.5,
            "paid": 0,
            "price": 12.5,
        },
        {
            "barcode": "1001",
            "name": "Bob",
            "purchases": 8,
            "waste": None,
            "paid": 0,
            "price": 8,
        },
    ]

    # Act
    filtered, tooltips, status = main_page_callbacks.update_income_lookup(
        "1000", rows
    )

    # Assert
    assert filtered == [rows[0]]
    assert filtered[0]["price"] == 12.5
    assert tooltips[0]["price"]["value"] == "12.5"
    assert status == ""


def test_income_lookup_callback_reports_no_match():
    # Arrange
    rows = [{"barcode": "1000", "name": "Alice", "price": 12.5}]

    # Act
    filtered, tooltips, status = main_page_callbacks.update_income_lookup(
        "missing", rows
    )

    # Assert
    assert filtered == []
    assert tooltips == []
    assert status == "No matching user."


def test_economy_layout_reuses_one_income_snapshot(monkeypatch, temp_db):
    # Arrange
    _load_transaction_data(temp_db)
    expected_rows = get_income()
    income_calls = 0

    def tracked_get_income():
        nonlocal income_calls
        income_calls += 1
        return copy.deepcopy(expected_rows)

    monkeypatch.setattr(main_layout, "get_income", tracked_get_income)

    # Act
    layout = main_layout.transaction_settings_layout()

    # Assert
    income_table = _find_component(layout, "income_table")
    income_store = _find_component(layout, "income_table_all_rows")
    income_search = _find_component(layout, "income_search")
    assert income_calls == 1
    assert income_table.data == expected_rows
    assert income_store.data == expected_rows
    assert income_search.placeholder == "Type a name or scan a barcode"


def test_payment_modal_stays_closed_when_economy_tab_renders(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="export_payments_btn"),
    )

    # Act
    result = main_page_callbacks.control_payments_modal(
        None, None, 0, "Up", 0, []
    )

    # Assert
    assert result == (no_update, no_update, no_update)


def test_selected_transaction_uses_sorted_virtual_table_position():
    # Arrange
    sorted_rows = [
        {
            "barcode_user": "1001",
            "barcode_prod": "102",
            "timestamp": "26/07/2026 11:00:00",
        },
        {
            "barcode_user": "1000",
            "barcode_prod": "101",
            "timestamp": "26/07/2026 10:00:00",
        },
    ]

    # Act
    selected = main_page_callbacks.get_selected_transaction(sorted_rows, [1])

    # Assert
    assert selected == sorted_rows[1]


def test_remove_transaction_button_requires_selection(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="remove_transaction_btn"),
    )

    # Act
    result = main_page_callbacks.control_transaction_removal(
        1, None, None, [], [], None, None, []
    )

    # Assert
    assert result[:4] == (no_update, no_update, no_update, no_update)
    assert "Select a transaction" in result[4][0]["msg"]


def test_remove_transaction_confirmation_shows_transaction_details(
    monkeypatch, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    transaction = temp_db.transactions.iloc[0].to_dict()
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="remove_transaction_btn"),
    )

    # Act
    result = main_page_callbacks.control_transaction_removal(
        1, None, None, [transaction], [0], None, None, []
    )

    # Assert
    assert result[0] is True
    assert result[2] == transaction
    summary = str(result[1])
    assert "Alice (1000)" in summary
    assert "Beer (101)" in summary
    assert "26/07/2026 10:00:00" in summary
    assert result[4] is no_update


def test_cancel_transaction_removal_changes_nothing(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="cancel_remove_transaction"),
    )
    before = temp_db.transactions.to_dict(orient="records")

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, 1, None, None, None, before[0], 2, []
    )

    # Assert
    assert result == (False, no_update, None, no_update, no_update)
    assert temp_db.transactions.to_dict(orient="records") == before
    assert not backup_dir.exists()


def test_confirm_transaction_removal_deletes_one_match_backs_up_and_blocks_export(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    duplicate = {
        "barcode_user": "1000",
        "barcode_prod": "101",
        "timestamp": "26/07/2026 10:00:00",
    }
    _load_transaction_data(temp_db, [duplicate.copy(), duplicate.copy()])
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_remove_transaction"),
    )
    stock_before = temp_db.prods.iloc[0].to_dict()

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, None, 1, None, None, duplicate, 4, []
    )

    # Assert
    assert result == (False, no_update, None, 5, no_update)
    assert temp_db.transactions.to_dict(orient="records") == [duplicate]
    assert temp_db.prods.iloc[0].to_dict() == stock_before
    assert get_last_stock_update_at() == ""
    warning = main_page_callbacks._validate_payment_export_stock_freshness()
    assert warning.block_export is True
    assert "Update stock" in warning.message

    backups = list(backup_dir.glob("*_pre_transaction_delete_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        backed_up_stock_timestamp = con.execute(
            "SELECT last_stock_update_at FROM settings"
        ).fetchone()[0]
    finally:
        con.close()
    assert backed_up_count == 2
    assert backed_up_stock_timestamp == "2026-07-26T10:30:00"


def test_confirm_missing_transaction_reports_error_without_changing_anything(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_remove_transaction"),
    )
    missing = {
        "barcode_user": "1000",
        "barcode_prod": "101",
        "timestamp": "26/07/2026 12:00:00",
    }
    transactions_before = temp_db.transactions.to_dict(orient="records")
    settings_before = temp_db.settings.to_dict(orient="records")
    products_before = temp_db.prods.to_dict(orient="records")

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, None, 1, None, None, missing, 9, []
    )

    # Assert
    assert result[:4] == (no_update, no_update, no_update, no_update)
    assert "no longer exists" in result[4][0]["msg"]
    assert temp_db.transactions.to_dict(orient="records") == transactions_before
    assert temp_db.settings.to_dict(orient="records") == settings_before
    assert temp_db.prods.to_dict(orient="records") == products_before
    assert not backup_dir.exists()


def test_transaction_removal_write_failure_rolls_back_data_and_stock_timestamp(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    transaction = temp_db.transactions.iloc[0].to_dict()
    transactions_before = temp_db.transactions.to_dict(orient="records")
    settings_before = temp_db.settings.to_dict(orient="records")
    monkeypatch.setattr(
        temp_db._settings_table,
        "set",
        lambda _rows: ("settings", [{"last_stock_update_at": ""}]),
    )

    # Act
    with pytest.raises(ValueError, match="Failed to update settings"):
        main_page_callbacks.remove_transaction(transaction)

    # Assert
    assert temp_db.transactions.to_dict(orient="records") == transactions_before
    assert temp_db.settings.to_dict(orient="records") == settings_before
    assert len(list(backup_dir.glob("*_pre_transaction_delete_*.db"))) == 1


def test_removing_final_transaction_refreshes_live_calculations(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    transaction = temp_db.transactions.iloc[0].to_dict()
    monkeypatch.setattr(
        main_page_callbacks,
        "BACKUP_DIR",
        str(tmp_path / "backups"),
    )
    assert get_revenue() == 10
    assert get_income()[0]["#products"] == 1
    assert get_waste_table()[0]["Amount Sold"] == 1

    # Act
    main_page_callbacks.remove_transaction(transaction)

    # Assert
    assert temp_db.transactions.empty
    assert get_revenue() == 0
    assert get_income()[0]["#products"] == 0
    assert get_waste_table()[0]["Amount Sold"] == 0
    assert get_waste_table()[0]["Waste"] == 2


def test_transaction_removal_revision_refreshes_settings_layouts(
    monkeypatch, temp_db
):
    # Arrange
    marker = object()
    monkeypatch.setattr(main_layout.time, "sleep", lambda _: None)
    monkeypatch.setattr(main_layout, "user_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "product_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "transaction_settings_layout", lambda: marker)

    # Act
    result = main_layout.update_settings_layout(
        None, False, None, None, None, None, None, 1
    )

    # Assert
    assert result == (marker, marker, marker)


def test_successful_import_commits_settings_and_data_after_backup(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended success path: backup first, then commit settings/import."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id={"index": "users", "type": "database_upload"}),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    csv = "barcode,name,rank,team\n1001,Imported User,Member,B\n"
    encoded_csv = _encoded_csv(csv)

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        None,
        True,
        [encoded_csv, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_category_purchasers",
        50,
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[0] is True
    assert result.values[2] is False
    assert Container.get(Database).users.iloc[0]["name"] == "Imported User"
    assert Container.get(Database).settings.iloc[0]["password"] == "pw"

    backups = list(backup_dir.glob("*_pre_import_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_user = con.execute("SELECT name FROM users").fetchone()[0]
    finally:
        con.close()
    assert backed_up_user == "Original User"


def test_non_upload_settings_trigger_does_not_reimport_stale_upload(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended trigger behavior: upload contents are used only on upload."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_new_password"),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    stale_upload = _encoded_csv("barcode,name,rank,team\n1001,Imported User,Member,B\n")

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        1,
        True,
        [stale_upload, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_category_purchasers",
        50,
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[-1] is True
    assert Container.get(Database).users.iloc[0]["name"] == "Original User"
    assert not backup_dir.exists()


def test_failed_import_rolls_back_changes_but_keeps_pre_import_backup(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended failure path: rollback DB changes, keep the safety copy."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id={"index": "users", "type": "database_upload"}),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    invalid_upload = _encoded_csv("barcode,name,rank,team\n999,Bad User,Member,B\n")

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        None,
        False,
        [invalid_upload, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_all",
        50,
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[2] is True
    assert Container.get(Database).users.iloc[0]["name"] == "Original User"
    assert Container.get(Database).settings.iloc[0]["password"] == "OLProgram"
    assert Container.get(Database).settings.iloc[0]["waste_strategy"] == (
        "equal_category_purchasers"
    )

    backups = list(backup_dir.glob("*_pre_import_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_user = con.execute("SELECT name FROM users").fetchone()[0]
    finally:
        con.close()
    assert backed_up_user == "Original User"
