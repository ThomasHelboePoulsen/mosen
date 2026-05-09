from typing import Optional


class Container:
    """Global object container for dependency management."""
    _db: Optional["Database"] = None

    @classmethod
    def set_db(cls, db: "Database") -> None:
        """Register a Database instance."""
        cls._db = db

    @classmethod
    def get_db(cls) -> "Database":
        """Get the registered Database instance. Raises RuntimeError if not initialized."""
        if cls._db is None:
            raise RuntimeError("Database not initialized. Call Container.set_db() first.")
        return cls._db

    @classmethod
    def reset(cls) -> None:
        """Reset container (primarily for testing)."""
        cls._db = None


def init_db(db_file: str = "beerbase.db") -> None:
    """Initialize container with real database."""
    #Ok this import is shit, but at some point this class will be container for any types, so this can be removed.
    from src.data_connection import Database
    db = Database(db_file)
    Container.set_db(db)
