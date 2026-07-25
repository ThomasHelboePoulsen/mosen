import pandas as pd


def validate_import(db, table_name, data):
    """Validate rules specific to replacing a table from a CSV import."""

    table = db.get_table(table_name)
    column_names = [column.name for column in table.columns]
    expected_columns = set(column_names)
    required_columns = {
        column.name for column in table.columns if column.required
    }
    uploaded_columns = set(data.columns)
    if table.get().empty:
        valid_headers = (
            required_columns.issubset(uploaded_columns)
            and uploaded_columns.issubset(expected_columns)
        )
        header_error = (
            "Initial imports must include the required columns and no unknown "
            "columns. Required: "
            + ", ".join(
                name for name in column_names if name in required_columns
            )
            + ". Allowed: "
            + ", ".join(column_names)
        )
    else:
        valid_headers = uploaded_columns == expected_columns
        header_error = (
            "Replacement imports must contain exactly these columns: "
            + ", ".join(column_names)
        )

    if not valid_headers:
        return [{"error": header_error}]

    reference_columns = {
        "users": "barcode_user",
        "prods": "barcode_prod",
    }
    if table_name not in reference_columns:
        return []

    transactions = db._transaction_table.get()
    reference_column = reference_columns[table_name]
    referenced = pd.to_numeric(
        transactions[reference_column], errors="coerce"
    ).dropna().astype(int).value_counts()
    available = set(
        pd.to_numeric(data.get("barcode", pd.Series(dtype=float)), errors="coerce")
        .dropna()
        .astype(int)
    )
    label = "user" if table_name == "users" else "product"
    return [
        {
            "barcode": int(barcode),
            "error": f"Missing {label} referenced by {count} transaction(s)",
        }
        for barcode, count in referenced.sort_index().items()
        if barcode not in available
    ]
