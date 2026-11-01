import sqlite3
import time
from contextlib import closing

from src.database.data_connection import Database


# Ten times the expected 300 users * 16 purchases. Like the scan performance
# tests, this is a machine-dependent regression budget, not a hardware guarantee.
PURCHASE_COUNT = 48_000
BACKUP_LIMIT_SECONDS = 0.5


def test_large_trip_backup_is_fast_enough(tmp_path):
    db = Database(str(tmp_path / "large_trip.db"))
    with closing(sqlite3.connect(db.data_file)) as con:
        con.executemany(
            "INSERT INTO users VALUES (?, ?, ?, ?, 0, -1, 0)",
            [(1000 + i, f"User {i}", "Member", f"Team {i % 10}") for i in range(300)],
        )
        con.executemany(
            "INSERT INTO prods VALUES (?, ?, ?, ?, ?, ?)",
            [(100 + i, f"Product {i}", "12.50", "Drink", "500", "500") for i in range(100)],
        )
        con.executemany(
            "INSERT INTO transactions VALUES (?, ?, ?)",
            [(1000 + i % 300, 100 + i % 100, "01/11/2026 12:00:00") for i in range(PURCHASE_COUNT)],
        )
        con.commit()

    for attempt in range(3):
        destination = tmp_path / f"snapshot_{attempt}.db"
        start = time.perf_counter()
        db.backup_to(str(destination))
        elapsed = time.perf_counter() - start

        print(f"Large trip backup {attempt + 1}: {elapsed:.3f}s")
        assert elapsed < BACKUP_LIMIT_SECONDS, (
            f"Backup of {PURCHASE_COUNT:,} purchases took {elapsed:.3f}s, "
            f"expected under {BACKUP_LIMIT_SECONDS:.3f}s"
        )
        with closing(sqlite3.connect(destination)) as snapshot:
            assert snapshot.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert snapshot.execute("SELECT COUNT(*) FROM transactions").fetchone() == (PURCHASE_COUNT,)
