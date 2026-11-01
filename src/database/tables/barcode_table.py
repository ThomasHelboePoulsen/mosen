from src.database.tables.base_table import BaseTable


class BarcodeTable(BaseTable):
    """Table with one barcode column and a matching membership index."""

    _barcode_cache: frozenset[int] = frozenset()

    def _refresh_cache(self) -> None:
        with self.connection._lock:
            cache = self._read_cache()
            barcodes = frozenset(map(int, cache["barcode"]))
            self._cache = cache
            self._barcode_cache = barcodes

    def contains_barcode(self, barcode: int) -> bool:
        """Check a normalized integer barcode without copying table data."""
        with self.connection._lock:
            return barcode in self._barcode_cache
