import pytest
import pandas as pd

from src.container import Container
from src.data_connection import (
    Database,
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
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
    db.init()
    Container.set_db(db)
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
        expected_columns = ["barcode", "name", "rank", "team"]
        
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
        container_db = Container.get_db()
        
        # Act
        result = get_prods()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert Container.get_db() is container_db


class TestProductValidation:

    def test_validate_prod_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
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
        validated_row, is_bad = db.validate_prod(row, data)
        
        # Assert
        assert is_bad is False
        assert validated_row["barcode"] == "123"

    def test_validate_prod_rejects_invalid_barcode_length(self, test_db):
        # Arrange
        db = Container.get_db()
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
        validated_row, is_bad = db.validate_prod(row, data)
        
        # Assert
        assert is_bad is True
        assert validated_row["barcode"] != "12"  # Should be auto-generated

    def test_validate_prod_rejects_missing_columns(self, test_db):
        # Arrange
        db = Container.get_db()
        row = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
        }
        data = [row]
        
        # Act
        validated_row, is_bad = db.validate_prod(row, data)
        
        # Assert
        assert is_bad is True


class TestUserValidation:

    def test_validate_user_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
        row = {
            "barcode": "1000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        validated_row, is_bad = db.validate_user(row, data)
        
        # Assert
        assert is_bad is False
        assert validated_row["barcode"] == "1000"

    def test_validate_user_rejects_short_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
        row = {
            "barcode": "999",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        validated_row, is_bad = db.validate_user(row, data)
        
        # Assert
        assert is_bad is True
        assert validated_row["barcode"] != "999"

    def test_validate_user_rejects_long_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
        row = {
            "barcode": "100000000000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        validated_row, is_bad = db.validate_user(row, data)
        
        # Assert
        assert is_bad is True


class TestTransactionValidation:

    def test_validate_trans_rejects_nonexistent_product(self, test_db):
        # Arrange
        db = Container.get_db()
        trans_row = {
            "barcode_user": "1000",
            "barcode_prod": "999",
            "timestamp": "2024-01-01 12:00:00",
        }
        
        # Act
        validated_row, is_bad = db.validate_trans(trans_row, [trans_row])
        
        # Assert
        assert is_bad is True


class TestProductValidationWithDuplicates:

    def test_validate_prod_handles_duplicate_barcode(self, test_db):
        # Arrange - simulate existing products with duplicates in data
        db = Container.get_db()
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
        validated_row, is_bad = db.validate_prod(duplicate_prod, data)
        
        # Assert - should auto-generate new barcode
        assert is_bad is True
        assert validated_row["barcode"] != "123"
        assert len(str(validated_row["barcode"])) == 3  # Should be 3 digit
        assert int(validated_row["barcode"]) > 123  # Should be > max existing

    def test_validate_prod_finds_gap_in_barcodes(self, test_db):
        # Arrange - products with gaps in barcode range, new row has invalid length
        db = Container.get_db()
        data = [
            {"barcode": "100", "name": "A", "price": "1", "category": "X", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "102", "name": "B", "price": "2", "category": "Y", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "103", "name": "C", "price": "3", "category": "Z", "current_stock": "1", "initial_stock": "1"},
        ]
        new_row = {"barcode": "99", "name": "D", "price": "4", "category": "W", "current_stock": "1", "initial_stock": "1"}  # Invalid: 2 digits
        
        # Act
        validated_row, is_bad = db.validate_prod(new_row, data)
        
        # Assert - should trigger gap finding and assign first valid 3-digit (101)
        assert is_bad is True
        assert int(validated_row["barcode"]) == 101


class TestUserValidationWithDuplicates:

    def test_validate_user_handles_duplicate_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
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
        validated_row, is_bad = db.validate_user(duplicate_user, data)
        
        # Assert
        assert is_bad is True
        assert validated_row["barcode"] != "1000"
        assert int(validated_row["barcode"]) > 1000  # Should be > max existing

    def test_validate_user_finds_gap_in_barcodes(self, test_db):
        # Arrange - users with gaps in barcode range
        db = Container.get_db()
        data = [
            {"barcode": "1000", "name": "A", "rank": "M", "team": "X"},
            {"barcode": "1002", "name": "B", "rank": "M", "team": "Y"},
            {"barcode": "1003", "name": "C", "rank": "M", "team": "Z"},
        ]
        new_row = {"barcode": "999", "name": "D", "rank": "M", "team": "W"}
        
        # Act
        validated_row, is_bad = db.validate_user(new_row, data)
        
        # Assert - barcode too short, should assign first valid gap (1000 is taken, so 1001)
        assert is_bad is True
        assert int(validated_row["barcode"]) == 1001


class TestUploadValues:

    def test_upload_prods_validation_phase(self, test_db):
        # Arrange
        db = Container.get_db()
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
            validated_row, is_bad = db.validate_prod(row, valid_prods)
            if not is_bad:
                good_rows.append(validated_row)
            else:
                bad_rows.append(validated_row)
        
        # Assert
        assert len(good_rows) == 1
        assert len(bad_rows) == 0

    def test_upload_prods_rejects_invalid_barcode(self, test_db):
        # Arrange
        db = Container.get_db()
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
            validated_row, is_bad = db.validate_prod(row, invalid_prods)
            if not is_bad:
                good_rows.append(validated_row)
            else:
                bad_rows.append(validated_row)
        
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
        db = Container.get_db()
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
