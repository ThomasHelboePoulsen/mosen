from dash import dcc

from src import main_layout
from src.modals import bad_rows_mdl


def _walk_components(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        yield from _walk_components(child)


def _find_component_by_id(component, target_id):
    return next(
        (
            child
            for child in _walk_components(component)
            if getattr(child, "id", None) == target_id
        ),
        None,
    )


def _text_content(component):
    return " ".join(
        child
        for child in _walk_components(component)
        if isinstance(child, str)
    )


def test_database_transfer_guidance_is_grouped_with_all_uploads(temp_db):
    layout = main_layout.settings_settings_layout()

    section = _find_component_by_id(layout, "database_transfer_section")
    upload_ids = {
        component.id["index"]
        for component in _walk_components(section)
        if isinstance(component, dcc.Upload)
    }

    assert upload_ids == {"users", "prods", "transactions"}
    assert "Database import / export" in _text_content(section)
    assert "download the current table from its tab" in _text_content(section)
    assert "Uploads apply one table at a time" in _text_content(section)
    assert _find_component_by_id(section, "waste_strategy") is None


def test_bad_row_tables_show_error_and_uploaded_fields(temp_db):
    modal = bad_rows_mdl()
    expected_columns = {
        "users": [
            "error",
            "barcode",
            "name",
            "rank",
            "team",
            "is_guest",
            "waste_cents",
            "paid_cents",
        ],
        "prods": [
            "error",
            "barcode",
            "name",
            "price",
            "category",
            "current_stock",
            "initial_stock",
        ],
        "transactions": ["error", "barcode_user", "barcode_prod", "timestamp"],
    }

    for table_name, expected in expected_columns.items():
        table = _find_component_by_id(
            modal,
            {"index": table_name, "type": "bad_rows_table"},
        )
        assert [column["id"] for column in table.columns] == expected
