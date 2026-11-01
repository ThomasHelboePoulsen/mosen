"""Transaction append validation must not materialize the purchase history."""

import pandas as pd
import pytest


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


@pytest.mark.parametrize("as_dataframe", [False, True])
def test_append_preserves_history_without_converting_it_to_records(
    temp_db, transaction_table, monkeypatch, as_dataframe,
):
    rows = [_transaction(), _transaction()]
    data = pd.DataFrame(rows) if as_dataframe else rows

    def reject_history_conversion(*args, **kwargs):
        pytest.fail("Transaction append converted the old purchase history")

    monkeypatch.setattr(transaction_table._cache, "to_dict", reject_history_conversion)

    result = transaction_table.append(data)

    assert result == ("success", [])
    assert transaction_table.get().to_dict("records") == [_transaction(), *rows]
    stored = temp_db.get_query("SELECT * FROM transactions", list(transaction_table.get().columns))
    pd.testing.assert_frame_equal(transaction_table.get_untyped(), stored)


@pytest.mark.parametrize("invalid_values", [
    {"barcode_user": 1001},
    {"barcode_prod": 101},
    {"barcode_user": 100},
    {"timestamp": ""},
])
def test_append_rejects_entire_invalid_batch_and_preserves_history(
    temp_db, transaction_table, invalid_values,
):
    before = transaction_table.get_untyped()
    invalid_row = _transaction(**invalid_values)

    result, bad_rows = transaction_table.append([_transaction(), invalid_row])

    assert result == "transactions"
    assert bad_rows == [invalid_row]
    pd.testing.assert_frame_equal(transaction_table.get_untyped(), before)
    stored = temp_db.get_query("SELECT * FROM transactions", list(before.columns))
    pd.testing.assert_frame_equal(stored, before)


def test_append_rollback_preserves_history_in_database_and_cache(temp_db, transaction_table):
    before = transaction_table.get_untyped()

    def append_then_fail():
        assert transaction_table.append([_transaction()]) == ("success", [])
        raise RuntimeError("failure after append")

    with pytest.raises(RuntimeError, match="failure after append"):
        temp_db.execute_in_transaction(append_then_fail).raise_if_error()

    pd.testing.assert_frame_equal(transaction_table.get_untyped(), before)
    stored = temp_db.get_query("SELECT * FROM transactions", list(before.columns))
    pd.testing.assert_frame_equal(stored, before)


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
    stored = temp_db.get_query(f"SELECT * FROM {table_name}", list(before.columns))
    pd.testing.assert_frame_equal(stored, before)
