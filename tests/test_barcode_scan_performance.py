import time
import types
from threading import Event, Thread

import pandas as pd
import pytest
from dash import no_update

from src import trans_layout
from src.container import Container
from src.database.data_connection import Database


ACTION_LIMIT_SECONDS = 0.1
BURST_SCAN_COUNT = 20
BURST_LIMIT_SECONDS = 0.6
USER_BARCODE = "1000"
PRODUCT_BARCODE = "100"


@pytest.fixture
def scan_db(tmp_path):
    db = Database(str(tmp_path / "scan_performance.db"))
    Container.set(Database, db)
    _load_realistic_scan_data(db)
    yield db
    Container.reset()


def _load_realistic_scan_data(db):
    users = [
        {
            "barcode": 1000 + index,
            "name": f"User {index}",
            "rank": "Member",
            "team": f"Team {index % 8}",
            "is_guest": 0,
        }
        for index in range(150)
    ]
    products = [
        {
            "barcode": 100 + index,
            "name": f"Product {index}",
            "price": 1 + (index % 20) * 0.5,
            "category": f"Category {index % 6}",
            "current_stock": 500,
            "initial_stock": 600,
        }
        for index in range(80)
    ]
    transactions = [
        {
            "barcode_user": 1000 + (index % 150),
            "barcode_prod": 100 + (index % 80),
            "timestamp": (
                f"01/01/2026 {10 + (index // 3600):02d}:"
                f"{(index // 60) % 60:02d}:{index % 60:02d}"
            ),
        }
        for index in range(2000)
    ]

    db.upload_values_raises(pd.DataFrame(users), "users")
    db.upload_values_raises(pd.DataFrame(products), "prods")
    db._transaction_table.append(pd.DataFrame(transactions))


def _assert_runs_under(label, limit_seconds, action):
    start = time.perf_counter()
    result = action()
    elapsed = time.perf_counter() - start
    assert elapsed < limit_seconds, (
        f"{label} took {elapsed:.3f}s, expected under {limit_seconds:.3f}s"
    )
    return result


def _set_trigger(monkeypatch, trigger_id):
    monkeypatch.setattr(
        trans_layout,
        "ctx",
        types.SimpleNamespace(triggered_id=trigger_id),
    )


def _open_basket(monkeypatch, user_barcode=USER_BARCODE):
    _set_trigger(monkeypatch, "new_trans_inp")
    return trans_layout.open_trans_modal(1, None, user_barcode, None, [])


def _scan_product(monkeypatch, product_barcode=PRODUCT_BARCODE, user_barcode=USER_BARCODE):
    _set_trigger(monkeypatch, "prod_barcode")
    return trans_layout.new_trans(1, product_barcode, user_barcode, [])


def _submit_basket(monkeypatch, user_barcode=USER_BARCODE):
    _set_trigger(monkeypatch, "prod_barcode")
    return trans_layout.open_trans_modal(None, 1, user_barcode, user_barcode, [])


def _load_temporary_basket(db, product_count):
    db.upload_values_raises(
        pd.DataFrame(
            [
                {
                    "barcode_prod": str(100 + (index % 80)),
                    "name": f"Product {index % 80}",
                }
                for index in range(product_count)
            ]
        ),
        "temporary",
    )


def test_scan_user_barcode_opens_basket_under_action_limit(scan_db, monkeypatch):
    # Arrange
    _open_basket(monkeypatch, "1001")

    # Act
    result = _assert_runs_under(
        "scan user barcode to open basket",
        ACTION_LIMIT_SECONDS,
        lambda: _open_basket(monkeypatch),
    )

    # Assert
    assert result[0] is True
    assert result[3] is no_update


def test_scan_product_barcode_adds_to_basket_under_action_limit(scan_db, monkeypatch):
    # Arrange
    _open_basket(monkeypatch)
    _scan_product(monkeypatch, "101")
    scan_db.upload_values_raises([], "temporary")

    # Act
    result = _assert_runs_under(
        "scan product barcode into open basket",
        ACTION_LIMIT_SECONDS,
        lambda: _scan_product(monkeypatch),
    )

    # Assert
    assert result[1] == ""
    assert result[2] is no_update
    assert len(scan_db._temporary_table.get()) == 1


def test_scan_user_barcode_submits_purchase_under_action_limit(scan_db, monkeypatch):
    # Arrange
    _load_temporary_basket(scan_db, product_count=10)
    transactions_before = len(scan_db._transaction_table.get())

    # Act
    result = _assert_runs_under(
        "scan user barcode to submit basket",
        ACTION_LIMIT_SECONDS,
        lambda: _submit_basket(monkeypatch),
    )

    # Assert
    assert result[0] is False
    assert result[3] is no_update
    assert len(scan_db._transaction_table.get()) == transactions_before + 10


def test_rapid_product_scans_drain_under_burst_limit(scan_db, monkeypatch):
    # Arrange
    _open_basket(monkeypatch)
    start_event = Event()
    results = []
    errors = []

    def scan_worker(index):
        start_event.wait()
        try:
            results.append(_scan_product(monkeypatch, str(100 + (index % 80))))
        except Exception as exc:
            errors.append(exc)

    threads = [Thread(target=scan_worker, args=(index,)) for index in range(BURST_SCAN_COUNT)]
    for thread in threads:
        thread.start()

    # Act
    start = time.perf_counter()
    start_event.set()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - start

    # Assert
    assert elapsed < BURST_LIMIT_SECONDS, (
        f"{BURST_SCAN_COUNT} rapid product scans drained in {elapsed:.3f}s, "
        f"expected under {BURST_LIMIT_SECONDS:.3f}s"
    )
    assert errors == []
    assert len(results) == BURST_SCAN_COUNT
    assert all(result[2] is no_update for result in results)
    assert len(scan_db._temporary_table.get()) == BURST_SCAN_COUNT
