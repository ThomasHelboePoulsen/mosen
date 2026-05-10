import pytest
import pandas as pd
from src.container import Container
from src.data_connection import Database
from src.tables.product import ProductTable


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestProductTableBasics:

    def test_product_table_creates_table(self, test_db):
        # Arrange & Act
        table = ProductTable(test_db._connection)
        
        # Assert - table should exist
        assert test_db._connection.table_exists('prods')

    def test_get_returns_empty_dataframe(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        
        # Act
        result = table.get()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert list(result.columns) == ["barcode", "name", "price", "category", "current_stock", "initial_stock"]

    def test_get_typed_returns_correct_dtypes(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        
        # Act
        result = table.get_typed()
        
        # Assert - empty but with correct dtypes
        assert result["barcode"].dtype == int
        assert result["name"].dtype == object  # str
        assert result["price"].dtype == float
        assert result["category"].dtype == object  # str
        assert result["current_stock"].dtype == int
        assert result["initial_stock"].dtype == int


class TestProductTableSet:

    def test_set_inserts_valid_products(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        assert len(table.get()) == 1

    def test_set_replaces_all_data(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data1 = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        data2 = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            }
        ]
        
        # Act
        table.set(data1)
        table.set(data2)
        
        # Assert - should only have second dataset
        result = table.get()
        assert len(result) == 1
        assert result.iloc[0]["barcode"] == "456"

    def test_set_rejects_invalid_barcode_length(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 12,  # Invalid: 2 digits
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert result == table.table_name
        assert len(bad_rows) == 1

    def test_set_detects_duplicates(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            },
            {
                "barcode": 123,  # Duplicate
                "name": "Beer Clone",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 5,
                "initial_stock": 15,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert len(bad_rows) == 1
        assert bad_rows[0]["barcode"] != 123  # Should be auto-corrected

    def test_set_handles_empty_values(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "",  # Empty
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert len(bad_rows) == 1

    def test_set_accepts_dataframe(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        df = pd.DataFrame([
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ])
        
        # Act
        result, bad_rows = table.set(df)
        
        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        assert len(table.get()) == 1



class TestProductTableGetTyped:

    def test_get_typed_returns_correct_types(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.50,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(data)
        
        # Act
        df = table.get_typed()
        
        # Assert
        assert df["barcode"].dtype == int
        assert df["name"].dtype == object
        assert df["price"].dtype == float
        assert df["current_stock"].dtype == int
        assert df["initial_stock"].dtype == int
        assert df.iloc[0]["barcode"] == 123
        assert df.iloc[0]["price"] == 5.50
