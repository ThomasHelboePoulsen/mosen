class Column():
    def __init__(self, name, pandas_dtype, required=True, default=None, is_primary_key=False):
        self.name = name
        self.pandas_dtype = pandas_dtype
        self.required = required
        self.default = default
        self.is_primary_key = is_primary_key

    def __repr__(self):
        return f"Column(name='{self.name}', pandas_dtype='{self.pandas_dtype}', required={self.required}, default={self.default}, is_primary_key={self.is_primary_key})"
    
class BarcodeColumn(Column):
    def __init__(self, name, pandas_dtype, min, max, required=True, default=None, is_primary_key=False):
        super().__init__(name, pandas_dtype, required, default, is_primary_key)
        self.min = min
        self.max = max
    
    def is_valid_barcode(self, value):
        """Check if value is a valid barcode within min/max range."""
        try:
            val = int(value)
            return self.min <= val <= self.max
        except (ValueError, TypeError):
            return False
