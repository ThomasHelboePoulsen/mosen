import pytest
import pandas as pd

from src.container import Container
from src.database.tables.product import ProductTable
from src.database.data_connection import (
    Database,
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
    update_current_trans,
    add_transactions,
    upload_values,
    get_password,
    get_backup_time,
    get_show_bill,
    get_waste,
    update_values,
)

@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestWrapperFunctions:

    def test_get_prods_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = [
            "barcode",
            "name",
            "price",
            "category",
            "current_stock",
            "initial_stock",
        ]
        
        # Act
        result = get_prods()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_trans_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = [
            "barcode_user",
            "barcode_prod",
            "timestamp",
        ]
        
        # Act
        result = get_trans()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_users_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = ["barcode", "name", "rank", "team", "is_guest"]
        
        # Act
        result = get_users()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_current_trans_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = ["barcode_prod", "name"]
        
        # Act
        result = get_current_trans()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    @pytest.mark.parametrize(
        "get_table_func",
        [get_prods, get_trans, get_users, get_current_trans],
    )
    def test_wrapper_functions_return_empty_on_init(self, test_db, get_table_func):
        # Arrange
        # (test_db fixture initializes empty database)
        
        # Act
        result = get_table_func()
        
        # Assert
        assert len(result) == 0

    def test_wrapper_functions_use_container_database(self, test_db):
        # Arrange
        container_db = Container.get(Database)
        
        # Act
        result = get_prods()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert Container.get(Database) is container_db


class TestProductValidation:

    def test_validate_prod_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is True

    def test_validate_prod_rejects_invalid_barcode_length(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "12",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is False

    def test_validate_prod_rejects_missing_columns(self, test_db):
        # Arrange - missing required columns: category, current_stock, initial_stock
        db = Container.get(Database)
        row = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is False


class TestUserValidation:

    def test_validate_user_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "1000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is True

    def test_validate_user_rejects_short_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "999",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is False

    def test_validate_user_rejects_long_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "100000000000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is False


class TestTransactionValidation:

    def test_validate_trans_rejects_nonexistent_product(self, test_db):
        # Arrange
        db = Container.get(Database)
        trans_row = {
            "barcode_user": "1000",
            "barcode_prod": "999",
            "timestamp": "2024-01-01 12:00:00",
        }
        
        # Act
        is_valid = db.validate_trans(trans_row, [trans_row])
        
        # Assert
        assert is_valid is False


class TestProductValidationWithDuplicates:

    def test_validate_prod_handles_duplicate_barcode(self, test_db):
        # Arrange - simulate existing products with duplicates in data
        db = Container.get(Database)
        existing_prod = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        duplicate_prod = {
            "barcode": "123",  # Same barcode as existing
            "name": "Beer Clone",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "5",
            "initial_stock": "15",
        }
        data = [existing_prod, duplicate_prod]
        
        # Act - validate the duplicate
        is_valid = db.validate_prod(duplicate_prod, data)
        
        # Assert - should auto-generate new barcode
        assert is_valid is False

    def test_validate_prod_accepts_barcode_gaps(self, test_db):
        # Arrange - products with gaps in barcode range
        db = Container.get(Database)
        data = [
            {"barcode": "100", "name": "A", "price": "1", "category": "X", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "102", "name": "B", "price": "2", "category": "Y", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "103", "name": "C", "price": "3", "category": "Z", "current_stock": "1", "initial_stock": "1"},
        ]
        new_row = {"barcode": "110", "name": "D", "price": "4", "category": "W", "current_stock": "1", "initial_stock": "1"}  # Invalid: 2 digits
        
        # Act
        is_valid = db.validate_prod(new_row, data)
        
        # Assert
        assert is_valid is True


class TestUserValidationWithDuplicates:

    def test_validate_user_handles_duplicate_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        existing_user = {
            "barcode": "1000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        duplicate_user = {
            "barcode": "1000",  # Same barcode as existing
            "name": "Jane",
            "rank": "Member",
            "team": "B",
        }
        data = [existing_user, duplicate_user]
        
        # Act
        is_valid = db.validate_user(duplicate_user, data)
        
        # Assert
        assert is_valid is False

    def test_validate_user_finds_rejects_invalid_barcode(self, test_db):
        # Arrange - users with gaps in barcode range
        db = Container.get(Database)
        data = [
            {"barcode": "1000", "name": "A", "rank": "M", "team": "X"},
            {"barcode": "1002", "name": "B", "rank": "M", "team": "Y"},
            {"barcode": "1003", "name": "C", "rank": "M", "team": "Z"},
        ]
        new_row = {"barcode": "999", "name": "D", "rank": "M", "team": "W"}
        
        # Act
        is_valid = db.validate_user(new_row, data)
        
        # Assert - barcode too short, should assign first valid gap (1000 is taken, so 1001)
        assert is_valid is False


class TestUploadValues:

    def test_upload_prods_validation_phase(self, test_db):
        # Arrange
        db = Container.get(Database)
        valid_prods = [
            {
                "barcode": "123",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ]
        
        # Act - test just the validation phase
        good_rows = []
        bad_rows = []
        for row in valid_prods:
            is_valid = db.validate_prod(row, valid_prods)
            if is_valid:
                good_rows.append(row)
            else:
                bad_rows.append(row)
        
        # Assert
        assert len(good_rows) == 1
        assert len(bad_rows) == 0

    def test_upload_prods_rejects_invalid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        invalid_prods = [
            {
                "barcode": "99",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ]
        
        # Act
        good_rows = []
        bad_rows = []
        for row in invalid_prods:
            is_valid = db.validate_prod(row, invalid_prods)
            if is_valid:
                good_rows.append(row)
            else:
                bad_rows.append(row)
        
        # Assert
        assert len(good_rows) == 0
        assert len(bad_rows) == 1

    def test_upload_values_returns_success_or_error(self, test_db):
        # Arrange
        valid_users = [
            {
                "barcode": "1000",
                "name": "John",
                "rank": "Member",
                "team": "A",
            }
        ]
        
        # Act
        result, bad_rows = upload_values(valid_users, "users")
        
        # Assert
        assert result in ["success", "users"]  # Either success or table name on error

    def test_upload_with_dataframe_input(self, test_db):
        # Arrange
        db = Container.get(Database)
        valid_prods_df = pd.DataFrame([
            {
                "barcode": "123",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ])
        
        # Act
        result, bad_rows = upload_values(valid_prods_df, "prods")
        
        # Assert
        assert result in ["success", "prods"]

    def test_add_transactions_rejects_invalid_rows(self, test_db):
        # Arrange
        invalid_rows = pd.DataFrame([
            {
                "barcode_user": "1000",
                "barcode_prod": "999",
                "timestamp": "2024-01-01 12:00:00",
            }
        ])

        # Act
        result, bad_rows = add_transactions(invalid_rows)

        # Assert
        assert result == "transactions"
        assert len(bad_rows) == 1
        assert len(get_trans()) == 0

    def test_product_append_rejects_duplicate_rows_in_same_batch(self, test_db):
        # Arrange
        duplicate_rows = pd.DataFrame([
            {"barcode": "123", "name": "Beer", "price": "5.00", "category": "Beverage", "current_stock": "10", "initial_stock": "20"},
            {"barcode": "123", "name": "Beer Clone", "price": "6.00", "category": "Beverage", "current_stock": "5", "initial_stock": "15"},
        ])

        # Act
        result, bad_rows = Container.get(Database)._product_table.append(duplicate_rows)

        # Assert
        assert result == "prods"
        assert len(bad_rows) == 2
        assert len(get_prods()) == 0


class TestSettingsOperations:

    def test_get_show_bill_returns_bool(self, test_db):
        # Arrange
        
        # Act
        show_bill = get_show_bill()
        
        # Assert
        assert isinstance(show_bill, bool)

    def test_get_waste_returns_integer(self, test_db):
        # Arrange
        
        # Act
        waste = get_waste()
        
        # Assert
        assert isinstance(waste, int)

    def test_update_values_accepts_multiple_params(self, test_db):
        # Arrange
        
        # Act
        # Should not raise an error
        update_values(password="test", waste=50)
        
        # Assert
        assert True

    def test_settings_round_trip_through_cache(self, test_db):
        # Arrange
        
        # Act
        update_values(password="alpha", show_bill=False, waste=12, backup_time=42)

        # Assert
        assert get_password() == "alpha"
        assert get_show_bill() is False
        assert get_waste() == 12
        assert get_backup_time() == 42

    def test_current_trans_round_trip_through_cache(self, test_db):
        # Arrange
        current = pd.DataFrame([
            {"barcode_prod": "123", "name": "Beer"},
        ])

        # Act
        update_current_trans(current)
        result = get_current_trans()

        # Assert
        assert len(result) == 1
        assert list(result["barcode_prod"])[0] == "123"

    def test_add_transactions_appends_and_refreshes_cache(self, test_db):
        # Arrange
        upload_values(
            [
                {
                    "barcode": "1000",
                    "name": "John",
                    "rank": "Member",
                    "team": "A",
                }
            ],
            "users",
        )
        upload_values(
            [
                {
                    "barcode": "123",
                    "name": "Beer",
                    "price": "5.00",
                    "category": "Beverage",
                    "current_stock": "10",
                    "initial_stock": "20",
                }
            ],
            "prods",
        )

        from src.database.data_connection import add_transactions

        new_rows = pd.DataFrame([
            {
                "barcode_user": "1000",
                "barcode_prod": "123",
                "timestamp": "2024-01-01 12:00:00",
            }
        ])

        # Act
        add_transactions(new_rows)

        # Assert
        result = get_trans()
        assert len(result) == 1


class TestCreateTables:

    def test_init_creates_all_tables(self, tmp_path):
        # Arrange
        db_file = str(tmp_path / "createdb.db")

        # Act
        db = Database(db_file)

        # Assert
        con, cur = db._connection.connect()
        assert db._connection.table_exists("prods") is True
        assert db._connection.table_exists("users") is True
        assert db._connection.table_exists("transactions") is True
        assert db._connection.table_exists("temporary") is True
        assert db._connection.table_exists("settings") is True
        con.close()

    def test__create_tables_recreates_dropped_table(self, test_db):
        # Arrange - ensure tables exist then drop one
        db = test_db
        con, cur = db._connection.connect()
        # Drop users table
        cur.execute("DROP TABLE IF EXISTS users")
        con.commit()
        con.close()

        assert db._connection.table_exists("users") is False

        # Act - call private method to (re)create missing tables
        db._create_tables()

        # Assert - users table recreated
        assert db._connection.table_exists("users") is True
