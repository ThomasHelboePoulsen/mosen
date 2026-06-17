import pytest
import pandas as pd
from unittest.mock import patch
from dash import no_update
from src.container import Container
from src.database.data_connection import Database, upload_values
from src.main_page_callbacks import edit_new_data_modals


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(data_file=db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


@pytest.fixture
def test_user_data():
    return pd.DataFrame([
        {
            "barcode": 1500,
            "name": "John Doe",
            "rank": "Admin",
            "team": "Team A",
            "is_guest": 0,
        }
    ])


@pytest.fixture
def test_product_data():
    return pd.DataFrame([
        {
            "barcode": 101,
            "name": "Beer",
            "price": 5.0,
            "category": "Beverage",
            "current_stock": 10,
            "initial_stock": 20,
        }
    ])


class TestDeleteUserByBarcode:

    @patch("src.main_page_callbacks.ctx")
    def test_deletes_user_and_returns_empty_table(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_delete"
        user_col_count = 6
        prod_col_count = len(temp_db._product_table.columns)

        # Act
        result = edit_new_data_modals(1, None, "users", 1500, [])

        # Assert
        remaining_users = temp_db._user_table.get()
        assert len(remaining_users) == 0
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * user_col_count
        assert result[3] == [no_update] * prod_col_count
        assert len(result[4]) == 0
        assert result[5] is no_update


class TestDeleteProductByBarcode:

    @patch("src.main_page_callbacks.ctx")
    def test_deletes_product_and_returns_empty_table(self, mock_ctx, temp_db, test_product_data):
        # Arrange
        upload_values(test_product_data, "prods")
        mock_ctx.triggered_id = "edit_modal_delete"
        user_col_count = 6
        prod_col_count = len(temp_db._product_table.columns)

        # Act
        result = edit_new_data_modals(1, None, "prods", 101, [])

        # Assert
        remaining_prods = temp_db._product_table.get()
        assert len(remaining_prods) == 0
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * user_col_count
        assert result[3] == [no_update] * prod_col_count
        assert result[4] is no_update
        assert len(result[5]) == 0


class TestDeleteWithInvalidBarcode:

    @patch("src.main_page_callbacks.ctx")
    def test_returns_unchanged_table_when_barcode_not_found(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_delete"

        # Act
        result = edit_new_data_modals(1, None, "users", 9999, [])

        # Assert
        remaining_users = temp_db._user_table.get()
        assert len(remaining_users) == 1
        assert remaining_users.iloc[0]["barcode"] == 1500
        assert len(result[4]) == 1


class TestEditBranch:
    """Test edit branch of edit_new_data_modals callback"""

    @patch("src.main_page_callbacks.ctx")
    def test_edit_user_populates_form(self, mock_ctx, temp_db, test_user_data):
        """Edit user should populate form with user data"""
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_edit"
        user_col_count = 6
        prod_col_count = len(temp_db._product_table.columns)

        # Act
        result = edit_new_data_modals(
            None,  # delete n_clicks
            1,  # edit n_clicks
            "users",  # table
            1500,  # barcode
            [],  # error_queue (added by decorator)
        )

        # Assert
        assert result[0] is True  # new_user_modal opens
        assert result[1] is False  # new_prod_modal stays closed
        # User form data: [barcode, name, rank, team, [1] if is_guest else [], paid]
        # Note: callback returns untyped data (strings) from get_users()
        assert result[2][0] == 1500  # barcode (untyped from get_users)
        assert result[2][1] == "John Doe"  # name
        assert result[2][2] == "Admin"  # rank
        assert result[2][3] == "Team A"  # team
        assert result[2][4] == []  # is_guest checkbox (empty list = unchecked)
        assert result[2][5] == 0  # paid amount
        assert result[3] == [no_update] * prod_col_count
        assert result[4] is no_update  # user_table data
        assert result[5] is no_update  # prod_table data

    @patch("src.main_page_callbacks.ctx")
    def test_edit_user_with_guest_flag(self, mock_ctx, temp_db):
        """Edit user with is_guest=1 should show checkbox as checked"""
        # Arrange
        guest_user = pd.DataFrame([
            {
                "barcode": 2000,
                "name": "Guest User",
                "rank": "Guest",
                "team": "None",
                "is_guest": 1,
            }
        ])
        upload_values(guest_user, "users")
        mock_ctx.triggered_id = "edit_modal_edit"

        # Act
        result = edit_new_data_modals(
            None,  # delete n_clicks
            1,  # edit n_clicks
            "users",  # table
            2000,  # barcode
            [],  # error_queue (added by decorator)
        )

        # Assert
        assert result[2][4] == [1]  # is_guest checkbox (checked)

    @patch("src.main_page_callbacks.ctx")
    def test_edit_product_populates_form(self, mock_ctx, temp_db, test_product_data):
        """Edit product should populate form with product data"""
        # Arrange
        upload_values(test_product_data, "prods")
        mock_ctx.triggered_id = "edit_modal_edit"
        user_col_count = 6
        prod_col_count = len(temp_db._product_table.columns)

        # Act
        result = edit_new_data_modals(
            None,  # delete n_clicks
            1,  # edit n_clicks
            "prods",  # table
            101,  # barcode
            [],  # error_queue (added by decorator)
        )

        # Assert
        assert result[0] is False  # new_user_modal stays closed
        assert result[1] is True  # new_prod_modal opens
        assert result[2] == [no_update] * user_col_count
        # Product form data is all fields from row: [barcode, name, price, category, current_stock, initial_stock]
        # Note: callback returns untyped data (strings) from get_prods()
        assert result[3][0] == 101  # barcode (untyped from get_prods)
        assert result[3][1] == "Beer"  # name
        assert result[3][2] == 5.0  # price (untyped)
        assert result[3][3] == "Beverage"  # category
        assert result[3][4] == 10  # current_stock (untyped)
        assert result[3][5] == 20  # initial_stock (untyped)
        assert result[4] is no_update  # user_table data
        assert result[5] is no_update  # prod_table data


class TestEdgeCases:

    @patch("src.main_page_callbacks.ctx")
    def test_edit_nonexistent_user_returns_all_no_update(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_edit"

        # Act
        result = edit_new_data_modals(None, 1, "users", 9999, [])

        # Assert
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * 6
        assert result[3] == [no_update] * len(temp_db._product_table.columns)
        assert result[4] is no_update
        assert result[5] is no_update

    @patch("src.main_page_callbacks.ctx")
    def test_no_triggered_id_returns_all_no_update(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = None

        # Act
        result = edit_new_data_modals(None, None, "users", 1500, [])

        # Assert
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * 6
        assert result[3] == [no_update] * len(temp_db._product_table.columns)
        assert result[4] is no_update
        assert result[5] is no_update

    @patch("src.main_page_callbacks.ctx")
    def test_delete_with_none_barcode_returns_all_no_update(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_delete"

        # Act
        result = edit_new_data_modals(1, None, "users", None, [])

        # Assert
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * 6
        assert result[3] == [no_update] * len(temp_db._product_table.columns)
        assert result[4] is no_update
        assert result[5] is no_update

    @patch("src.main_page_callbacks.ctx")
    def test_edit_with_none_barcode_returns_all_no_update(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_edit"

        # Act
        result = edit_new_data_modals(None, 1, "users", None, [])

        # Assert
        assert result[0] is no_update
        assert result[1] is no_update
        assert result[2] == [no_update] * 6
        assert result[3] == [no_update] * len(temp_db._product_table.columns)
        assert result[4] is no_update
        assert result[5] is no_update


class TestUploadFailureHandling:

    @patch("src.main_page_callbacks.ctx")
    def test_delete_calls_upload_with_filtered_data(self, mock_ctx, temp_db, test_user_data):
        # Arrange
        upload_values(test_user_data, "users")
        mock_ctx.triggered_id = "edit_modal_delete"
        db = Container.get(Database)
        
        # Mock db.upload_values_raises to track if it's called
        original_upload = db.upload_values_raises
        call_tracker = {"called": False, "data": None, "table": None}
        
        def mock_upload_values_raises(data, table):
            call_tracker["called"] = True
            call_tracker["data"] = data.copy() if hasattr(data, 'copy') else data
            call_tracker["table"] = table
            return original_upload(data, table)
        
        db.upload_values_raises = mock_upload_values_raises

        # Act
        result = edit_new_data_modals(1, None, "users", 1500, [])

        # Assert
        assert call_tracker["called"]
        assert len(call_tracker["data"]) == 0
        assert call_tracker["table"] == "users"
        assert len(result) == 7
