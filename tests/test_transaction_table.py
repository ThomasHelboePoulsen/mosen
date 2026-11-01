"""Transaction append validation must not materialize the purchase history."""

import pandas as pd
import pytest

from src.barcode import BarcodePartition


def _transaction(**overrides):
    return {
        "barcode_user": 1000,
        "barcode_prod": 100,
        "timestamp": "01/11/2026 12:00:00",
        **overrides,
    }


@pytest.fixture
def transaction_table(temp_db):
    temp_db.upload_values_raises(
        [{"barcode": 1000, "name": "Alice", "rank": "Member", "team": "A"}],
        "users",
    )
    temp_db.upload_values_raises(
        [{"barcode": 100, "name": "Beer", "price": 5.0, "category": "Drink",
          "current_stock": 10, "initial_stock": 20}],
        "prods",
    )
    table = temp_db.get_table("transactions")
    assert table.set([_transaction()]) == ("success", [])
    return table


def test_append_preserves_history_without_converting_it_to_records(
    transaction_table, monkeypatch,
):
    rows = [_transaction(), _transaction()]

    def reject_history_conversion(*args, **kwargs):
        pytest.fail("Transaction append converted the old purchase history")

    monkeypatch.setattr(transaction_table._cache, "to_dict", reject_history_conversion)

    result = transaction_table.append(rows)

    assert result == ("success", [])
    assert transaction_table.get().to_dict("records") == [_transaction(), *rows]


@pytest.mark.parametrize("invalid_values", [
    {"barcode_user": 1001},
    {"barcode_prod": 101},
    {"barcode_user": 100},
    {"timestamp": ""},
])
def test_append_rejects_entire_invalid_batch_and_preserves_history(
    transaction_table, invalid_values,
):
    before = transaction_table.get_untyped()
    invalid_row = _transaction(**invalid_values)

    result, bad_rows = transaction_table.append([_transaction(), invalid_row])

    assert result == "transactions"
    assert bad_rows == [invalid_row]
    pd.testing.assert_frame_equal(transaction_table.get_untyped(), before)


def test_append_rollback_preserves_history_in_database_and_cache(temp_db, transaction_table):
    before = transaction_table.get_untyped()

    def append_then_fail():
        assert transaction_table.append([_transaction()]) == ("success", [])
        raise RuntimeError("failure after append")

    with pytest.raises(RuntimeError, match="failure after append"):
        temp_db.execute_in_transaction(append_then_fail).raise_if_error()

    pd.testing.assert_frame_equal(transaction_table.get_untyped(), before)


def test_reference_checks_use_cached_barcodes_without_reading_tables(
    temp_db, transaction_table, monkeypatch,
):
    def reject_table_read(*args, **kwargs):
        pytest.fail("Barcode existence check copied a reference table")

    for name in ("users", "prods"):
        table = temp_db.get_table(name)
        monkeypatch.setattr(table, "get", reject_table_read)
        monkeypatch.setattr(table, "get_untyped", reject_table_read)

    assert temp_db.barcode_exists(1000, BarcodePartition.USER) is True
    assert temp_db.barcode_exists(100, BarcodePartition.PRODUCT) is True
    assert temp_db.barcode_exists(1001, BarcodePartition.USER) is False
    assert temp_db.barcode_exists(101, BarcodePartition.PRODUCT) is False
    assert transaction_table.append([_transaction(), _transaction()]) == ("success", [])
    assert len(transaction_table.get()) == 3


def test_barcode_exists_preserves_input_validation(temp_db, transaction_table):
    assert temp_db.barcode_exists("001000", BarcodePartition.USER)
    assert temp_db.barcode_exists("00100", BarcodePartition.PRODUCT)
    assert not temp_db.barcode_exists(100, BarcodePartition.USER)
    assert not temp_db.barcode_exists(1000, BarcodePartition.PRODUCT)

    for invalid_barcode in (None, "", "bad", True, 0, 100.5):
        assert not temp_db.barcode_exists(invalid_barcode, BarcodePartition.USER)
        assert not temp_db.barcode_exists(invalid_barcode, BarcodePartition.PRODUCT)


@pytest.mark.parametrize("table_name, invalid_values", [
    ("users", {"barcode": "1000", "name": "Different user"}),
    ("prods", {"barcode": "100", "name": "Different product"}),
    ("prods", {"barcode": "101", "name": "Beer"}),
])
def test_other_tables_still_reject_duplicates_against_existing_rows(
    temp_db, transaction_table, table_name, invalid_values,
):
    table = temp_db.get_table(table_name)
    before = table.get_untyped()
    duplicate = {**before.iloc[0].to_dict(), **invalid_values}

    result, bad_rows = table.append([duplicate])

    assert result == table_name
    assert bad_rows == [duplicate]
    pd.testing.assert_frame_equal(table.get_untyped(), before)
