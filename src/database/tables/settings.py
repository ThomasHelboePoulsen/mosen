from src.database.tables.base_table import BaseTable
from src.database.tables.column import Column


class SettingsTable(BaseTable):
    table_name = "settings"
    columns = [
        Column("password", str, required=True),
        Column("show_bill", str, required=True),
        Column("waste", str, required=True),
        Column("backup", str, required=True),
    ]

    create_sql = """
        CREATE TABLE settings (
            password varchar(255),
            show_bill varchar(255),
            waste varchar(255),
            backup varchar(255)
        )
    """

    default_row = {
        "password": "OLProgram",
        "show_bill": "True",
        "waste": "0",
        "backup": "10",
    }

    def ensure_defaults(self) -> None:
        """Ensure the settings table contains the expected default row."""
        with self.connection._lock:
            if self.get().empty:
                self.set([self.default_row.copy()])