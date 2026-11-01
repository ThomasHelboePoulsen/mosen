from contextlib import closing
import sqlite3

import pandas as pd
import pytest

from src.database.data_connection import Database, TransactionResult


@pytest.fixture(params=["users", "prods"])
def barcode_table(temp_db, request):
    return temp_db.get_table(request.param)


@pytest.fixture
def row(barcode_table):
    if barcode_table.table_name == "users":
        return {"barcode": 1000, "name": "Alice", "rank": "Member", "team": "A"}
    return {"barcode": 100, "name": "Beer", "price": 5.0, "category": "Drink",
            "current_stock": 10, "initial_stock": 20}


def test_empty_table_has_no_barcodes(barcode_table, row):
    assert not barcode_table.contains_barcode(row["barcode"])


def test_set_normalizes_barcodes(barcode_table, row):
    imported_row = {**row, "barcode": f"00{row['barcode']}"}

    barcode_table.set([imported_row])

    assert barcode_table.contains_barcode(row["barcode"])


def test_reopening_database_loads_barcodes(temp_db, barcode_table, row):
    barcode_table.set([row])

    reopened = Database(temp_db.data_file)
    reopened_table = reopened.get_table(barcode_table.table_name)

    assert reopened_table.contains_barcode(row["barcode"])


def test_append_keeps_old_and_new_barcodes(barcode_table, row):
    barcode_table.set([row])
    new_row = {**row, "barcode": row["barcode"] + 1, "name": "New entry"}

    result = barcode_table.append([new_row])

    assert result == ("success", [])
    assert barcode_table.contains_barcode(row["barcode"])
    assert barcode_table.contains_barcode(new_row["barcode"])


def test_replacement_import_removes_old_barcodes(temp_db, barcode_table, row):
    barcode_table.set([row])
    new_row = {**row, "barcode": row["barcode"] + 1}

    temp_db.upload_values_raises([new_row], barcode_table.table_name)

    assert not barcode_table.contains_barcode(row["barcode"])
    assert barcode_table.contains_barcode(new_row["barcode"])


def test_reset_clears_barcodes(barcode_table, row):
    barcode_table.set([row])

    barcode_table.set([])

    assert not barcode_table.contains_barcode(row["barcode"])
    assert barcode_table.get().empty


def test_invalid_batch_keeps_previous_barcodes(barcode_table, row):
    barcode_table.set([row])
    before = barcode_table.get()
    new_row = {**row, "barcode": row["barcode"] + 1, "name": "New entry"}
    invalid_row = {**row, "barcode": 0}

    result, bad_rows = barcode_table.append([new_row, invalid_row])

    assert result == barcode_table.table_name
    assert bad_rows == [invalid_row]
    assert barcode_table.contains_barcode(row["barcode"])
    assert not barcode_table.contains_barcode(new_row["barcode"])
    pd.testing.assert_frame_equal(barcode_table.get(), before)


def test_exception_rolls_back_barcode_edit(temp_db, barcode_table, row):
    barcode_table.set([row])
    new_row = {**row, "barcode": row["barcode"] + 1}

    def edit_then_fail():
        barcode_table.set([new_row])
        assert barcode_table.contains_barcode(new_row["barcode"])
        assert not barcode_table.contains_barcode(row["barcode"])
        raise RuntimeError("failed edit")

    with pytest.raises(RuntimeError, match="failed edit"):
        temp_db.execute_in_transaction(edit_then_fail).raise_if_error()

    assert barcode_table.contains_barcode(row["barcode"])
    assert not barcode_table.contains_barcode(new_row["barcode"])


def test_cancelled_transaction_rolls_back_barcode_edit(temp_db, barcode_table, row):
    barcode_table.set([row])
    new_row = {**row, "barcode": row["barcode"] + 1}

    def edit_then_cancel():
        barcode_table.set([new_row])
        assert barcode_table.contains_barcode(new_row["barcode"])
        assert not barcode_table.contains_barcode(row["barcode"])
        return TransactionResult(values=(), commit=False)

    temp_db.execute_in_transaction(edit_then_cancel).raise_if_error()

    assert barcode_table.contains_barcode(row["barcode"])
    assert not barcode_table.contains_barcode(new_row["barcode"])


def test_periodic_validation_refreshes_barcodes(temp_db, barcode_table, row):
    barcode_table.set([row])
    old_barcode = row["barcode"]
    new_barcode = old_barcode + 1
    with closing(sqlite3.connect(temp_db.data_file)) as connection:
        connection.execute(
            f"UPDATE {barcode_table.table_name} SET barcode = ? WHERE barcode = ?",
            (new_barcode, old_barcode),
        )
        connection.commit()

    changed = temp_db.validate_cache_hashes()

    assert changed == [barcode_table.table_name]
    assert not barcode_table.contains_barcode(old_barcode)
    assert barcode_table.contains_barcode(new_barcode)


def test_failed_refresh_keeps_both_caches(barcode_table, row, monkeypatch):
    barcode_table.set([row])
    before = barcode_table.get()
    invalid_cache = pd.DataFrame({"barcode": ["invalid"]})
    monkeypatch.setattr(barcode_table, "_read_cache", lambda: invalid_cache)

    with pytest.raises(ValueError):
        barcode_table._refresh_cache()

    assert barcode_table.contains_barcode(row["barcode"])
    pd.testing.assert_frame_equal(barcode_table.get(), before)
