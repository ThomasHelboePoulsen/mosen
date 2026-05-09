import pytest

from src.container import Container, init_db
from src.data_connection import Database


class TestContainer:
    """Tests for Container singleton object management."""

    def setup_method(self):
        Container.reset()

    def teardown_method(self):
        Container.reset()

    def test_set_db_registers_instance(self):
        # Arrange
        test_db = Database(":memory:")
        
        # Act
        Container.set_db(test_db)
        
        # Assert
        assert Container.get_db() is test_db

    def test_get_db_raises_error_when_not_initialized(self):
        # Arrange
        Container.reset()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Database not initialized"):
            Container.get_db()

    def test_reset_clears_registered_instance(self):
        # Arrange
        test_db = Database(":memory:")
        Container.set_db(test_db)
        
        # Act
        Container.reset()
        
        # Assert
        with pytest.raises(RuntimeError):
            Container.get_db()

    def test_init_db_creates_and_registers_database(self):
        # Arrange
        db_file = ":memory:"
        
        # Act
        init_db(db_file)
        retrieved_db = Container.get_db()
        
        # Assert
        assert isinstance(retrieved_db, Database)
        assert retrieved_db.data_file == db_file
