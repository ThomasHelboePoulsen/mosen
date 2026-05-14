import pytest
import pandas as pd
from unittest.mock import patch
from dash import no_update
from src.container import Container
from src.database.data_connection import Database, get_prods, get_trans, upload_values, add_transactions, update_values
from src.tables.prod_callbacks import add_row, validate_barcode_prod, open_prod_modal, open_stock
from src.analytics.product_calculations import calculate_waste


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestValidateBarcodeProduct:

    def test_validate_barcode_prod_rejects_string_when_not_editing(self, test_db):
        # Arrange & Act
        result = validate_barcode_prod("abc", None)
        # Assert
        assert result is True

    def test_validate_barcode_prod_rejects_non_integer(self, test_db):
        # Arrange & Act
        result = validate_barcode_prod("abc", None)
        # Assert
        assert result is True

    def test_validate_barcode_prod_rejects_not_3_digits(self, test_db):
        # Arrange & Act
        result_2 = validate_barcode_prod(12, None)
        result_4 = validate_barcode_prod(1234, None)
        
        # Assert
        assert result_2 is True
        assert result_4 is True

    def test_validate_barcode_prod_accepts_valid_3_digit_barcode(self, test_db):
        # Arrange & Act
        result = validate_barcode_prod(123, None)
        # Assert
        assert result is False

    def test_validate_barcode_prod_rejects_duplicate_barcode(self, test_db):
        # Arrange
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = validate_barcode_prod(123, None)
        
        # Assert
        assert result is True

    def test_validate_barcode_prod_allows_duplicate_when_editing_same(self, test_db):
        # Arrange
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = validate_barcode_prod(123, 123)
        
        # Assert
        assert result is False


class TestProdCallbacksAddRow:

    def test_add_row_creates_new_product(self, test_db):
        # Arrange
        vals = [456, "Soda", 3.0, "Beverage", 15, 30]
        
        # Act
        result, edit_value = add_row(1, None, vals, None)
        
        # Assert
        prods = get_prods()
        assert len(prods) == 1
        assert prods.iloc[0]["barcode"] == "456"
        assert prods.iloc[0]["name"] == "Soda"

    def test_add_row_with_edit_replaces_existing_product(self, test_db):
        # Arrange
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        vals = [456, "Wine", 8.0, "Alcohol", 5, 15]
        
        # Act
        result, edit_value = add_row(1, None, vals, 123)
        
        # Assert
        prods = get_prods()
        assert len(prods) == 1
        assert prods.iloc[0]["barcode"] == "456"
        assert prods.iloc[0]["name"] == "Wine"

    def test_add_row_no_cascade_on_new_product(self, test_db):
        # Arrange
        upload_values(
            pd.DataFrame([
                {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
            ]),
            "prods",
        )
        upload_values(
            pd.DataFrame([
                {"barcode": 1500, "name": "John", "rank": "Member", "team": "A", "is_guest": 0}
            ]),
            "users",
        )
        trans_data = [
            {"barcode_user": "1500", "barcode_prod": "123", "timestamp": "2024-01-01 12:00:00"}
        ]
        add_transactions(pd.DataFrame(trans_data))
        vals = [456, "Wine", 8.0, "Alcohol", 5, 15]
        
        # Act
        result, edit_value = add_row(1, None, vals, None)
        
        # Assert
        trans = get_trans()
        assert trans.iloc[0]["barcode_prod"] == "123"

    def test_add_row_with_n_clicks_none_returns_no_update(self, test_db):
        # Arrange
        vals = [456, "Wine", 8.0, "Alcohol", 5, 15]
        
        # Act
        result, edit_value = add_row(None, None, vals, None)
        
        # Assert
        assert result is no_update


class TestOpenProdModal:

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_prod_modal_generates_next_barcode(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "new_prod_btn"
        data = [
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20},
            {"barcode": 456, "name": "Wine", "price": 8.0, "category": "Alcohol", "current_stock": 5, "initial_stock": 10},
        ]
        test_db._product_table.set(pd.DataFrame(data))
        
        # Act
        is_open, barcode = open_prod_modal(1, 0, 0)
        
        # Assert
        assert is_open is True
        assert barcode == 457

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_prod_modal_default_barcode_when_empty(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "new_prod_btn"
        
        # Act
        is_open, barcode = open_prod_modal(1, 0, 0)
        
        # Assert
        assert is_open is True
        assert barcode == 101

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_prod_modal_closes_on_confirm(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_prod"
        
        # Act
        is_open, barcode = open_prod_modal(0, 1, 0)
        
        # Assert
        assert is_open is False


class TestOpenStock:

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_stock_updates_current_stock(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_new_stock"
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = open_stock(0, 1, [5])
        
        # Assert
        prods = get_prods()
        assert prods.iloc[0]["current_stock"] == "5"

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_stock_rejects_none_inputs(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_new_stock"
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = open_stock(0, 1, [None])
        
        # Assert
        prods = get_prods()
        assert prods.iloc[0]["current_stock"] == "10"

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_stock_rejects_negative_inputs(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_new_stock"
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = open_stock(0, 1, [-5])
        
        # Assert
        prods = get_prods()
        assert prods.iloc[0]["current_stock"] == "10"

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_stock_returns_false_on_success(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_new_stock"
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = open_stock(0, 1, [5])
        
        # Assert
        assert result is False

    @patch('src.tables.prod_callbacks.ctx')
    def test_open_stock_returns_no_update_on_validation_failure(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_new_stock"
        prod_data = pd.DataFrame([
            {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
        ])
        upload_values(prod_data, "prods")
        
        # Act
        result = open_stock(0, 1, [None])
        
        # Assert
        assert result is no_update
