import pytest
import sqlite3
from src.container import Container
from src.database.data_connection import Database, db_transaction

@pytest.fixture
def test_db(tmp_path):
    # Arrange: create Database and register in Container
    db_file = str(tmp_path / "tx_fixture.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()

def test_execute_in_transaction_rolls_back_on_exception(test_db):
    # Arrange
    db = test_db
    product_row = {
        'barcode': '999',
        'name': 'CrashBeer',
        'price': '1.00',
        'category': 'Crash',
        'current_stock': '5',
        'initial_stock': '5',
    }

    # Act
    def tx_body():
        db._product_table.set([product_row])
        raise RuntimeError('simulated crash')

    with pytest.raises(RuntimeError):
        db.execute_in_transaction(tx_body)

    # Assert - DB must not contain the row and cache must reflect that
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0

def test_db_transaction_decorator_rolls_back_and_refreshes_cache(test_db):
    # Arrange
    db = test_db
    product_row = {
        'barcode': '1234',
        'name': 'DecorBeer',
        'price': '2.00',
        'category': 'Decor',
        'current_stock': '3',
        'initial_stock': '3',
    }

    @db_transaction
    def callback_that_crashes():
        db._product_table.set([product_row])
        raise ValueError('boom in callback')

    # Act / Assert
    with pytest.raises(ValueError):
        callback_that_crashes()

    # Assert - no row persisted and cache empty
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0

def test_set_then_error_between_sets_rolls_back(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '200', 'name': 'A', 'price': '1.00', 'category': 'X', 'current_stock': '1', 'initial_stock': '1'}
    row2 = {'barcode': '201', 'name': 'B', 'price': '2.00', 'category': 'Y', 'current_stock': '1', 'initial_stock': '1'}

    # Act
    def tx_body():
        db._product_table.set([row1])
        # simulate crash between sets
        raise Exception('crash between sets')
        db._product_table.set([row2])

    with pytest.raises(Exception):
        db.execute_in_transaction(tx_body)

    # Assert - neither row should be persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0

def test_set_multiple_rows_commit_on_success(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '300', 'name': 'C', 'price': '3.00', 'category': 'Z', 'current_stock': '2', 'initial_stock': '2'}
    row2 = {'barcode': '301', 'name': 'D', 'price': '4.00', 'category': 'W', 'current_stock': '2', 'initial_stock': '2'}

    # Act
    def tx_body():
        db._product_table.set([row1])
        db._product_table.set([row1, row2])

    db.execute_in_transaction(tx_body)

    # Assert - both rows persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 2
    assert len(db._product_table.get()) == 2


def test_append_then_error_between_appends_rolls_back(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '400', 'name': 'E', 'price': '5.00', 'category': 'M', 'current_stock': '1', 'initial_stock': '1'}
    row2 = {'barcode': '401', 'name': 'F', 'price': '6.00', 'category': 'N', 'current_stock': '1', 'initial_stock': '1'}

    # Act
    def tx_body():
        db._product_table.append([row1])
        # simulate crash between appends
        raise Exception('crash between appends')
        db._product_table.append([row2])

    with pytest.raises(Exception):
        db.execute_in_transaction(tx_body)

    # Assert - neither row should be persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0


def test_append_multiple_rows_commit_on_success(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '500', 'name': 'G', 'price': '7.00', 'category': 'O', 'current_stock': '2', 'initial_stock': '2'}
    row2 = {'barcode': '501', 'name': 'H', 'price': '8.00', 'category': 'P', 'current_stock': '2', 'initial_stock': '2'}

    # Act
    def tx_body():
        db._product_table.append([row1])
        db._product_table.append([row2])

    db.execute_in_transaction(tx_body)

    # Assert - both rows persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 2
    assert len(db._product_table.get()) == 2
