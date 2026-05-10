from typing import Optional


class Container:
    """Global object container for dependency management."""
    _db: Optional["Database"] = None

    @classmethod
    def get_db(cls) -> "Database":
        """Get the registered Database instance."""
        if cls._db is None:
            raise RuntimeError("Database not initialized. Call Container.set_db() or init_db() first.")
        return cls._db
    
    @classmethod
    def set_db(cls, db) -> None:
        """Register a Database instance."""
        if not hasattr(db, '_connection'):
            raise TypeError("Expected Database object with _connection attribute")
        cls._db = db

    @classmethod
    def reset(cls) -> None:
        """Reset container (primarily for testing)."""
        cls._db = None


def init_db(db_file: str = "beerbase.db") -> None:
    """Initialize container with real database connection and create tables."""
    #Ok this import is shit, but at some point this class will be container for any types, so this can be removed.
    from src.data_connection import Database
    
    db = Database(db_file)
    db.init()
    Container.set_db(db)
