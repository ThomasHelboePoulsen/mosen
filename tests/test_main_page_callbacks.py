import base64
import io
import sqlite3
import types

from dash import no_update

from src import main_page_callbacks


TABLE_IDS = [
    {"index": "users"},
    {"index": "prods"},
    {"index": "transactions"},
]
USER_HEADER = "barcode,name,rank,team,is_guest,waste_cents,paid_cents\n"
PRODUCT_HEADER = "barcode,name,price,category,current_stock,initial_stock\n"


def _encoded_csv(csv):
    return "data:text/csv;base64," + base64.b64encode(
        csv.encode("utf-8")
    ).decode("ascii")


def _run_import(monkeypatch, contents, table_name, password="new-password"):
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(
            triggered_id={"index": table_name, "type": "database_upload"}
        ),
    )
    return main_page_callbacks.update_settings.__wrapped__(
        None,
        True,
        contents,
        TABLE_IDS,
        "equal_category_purchasers",
        50,
        password,
    )


def _seed_user(db):
    db.upload_values(
        [
            {
                "barcode": 1000,
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )


def test_payment_modal_stays_closed_when_economy_tab_renders(monkeypatch, temp_db):
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="export_payments_btn"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, None, 0, "Up", 0, []
    )

    assert result == (no_update, no_update, no_update)


def test_upload_applies_only_the_triggered_table_when_other_contents_are_stale(
    monkeypatch, tmp_path, temp_db
):
    _seed_user(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    stale_users = _encoded_csv(
        USER_HEADER + "1001,Stale User,Member,B,0,-1,0\n"
    )
    products = _encoded_csv(
        PRODUCT_HEADER + "101,New Product,10,Drinks,10,10\n"
    )

    result = _run_import(
        monkeypatch,
        [stale_users, products, None],
        table_name="prods",
    )

    assert result.error is None
    assert result.values[2] is False
    assert list(temp_db.users["name"]) == ["Original User"]
    assert list(temp_db.prods["name"]) == ["New Product"]
    assert temp_db.settings.iloc[0]["password"] == "new-password"
    assert len(list(backup_dir.glob("*_pre_import_*.db"))) == 1


def test_header_only_upload_clears_an_unreferenced_table(
    monkeypatch,
    tmp_path,
    temp_db,
):
    _seed_user(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))

    result = _run_import(
        monkeypatch,
        [_encoded_csv(USER_HEADER), None, None],
        table_name="users",
    )

    assert result.error is None
    assert result.values[2] is False
    assert temp_db.users.empty
    assert len(list(backup_dir.glob("*_pre_import_*.db"))) == 1


def test_settings_change_does_not_reapply_stale_upload_contents(
    monkeypatch,
    tmp_path,
    temp_db,
):
    _seed_user(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_new_password"),
    )
    stale_users = _encoded_csv(
        USER_HEADER + "1001,Stale User,Member,B,0,-1,0\n"
    )

    result = main_page_callbacks.update_settings.__wrapped__(
        1,
        True,
        [stale_users, None, None],
        TABLE_IDS,
        "equal_category_purchasers",
        50,
        "new-password",
    )

    assert result.error is None
    assert result.values[-1] is True
    assert list(temp_db.users["name"]) == ["Original User"]
    assert not backup_dir.exists()


def test_failed_upload_rolls_back_settings_but_keeps_pre_import_backup(
    monkeypatch, tmp_path, temp_db
):
    _seed_user(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    invalid_users = _encoded_csv(
        USER_HEADER + "999,Bad User,Member,B,0,-1,0\n"
    )

    result = _run_import(
        monkeypatch,
        [invalid_users, None, None],
        table_name="users",
    )

    assert result.error is None
    assert result.values[2] is True
    assert list(temp_db.users["name"]) == ["Original User"]
    assert temp_db.settings.iloc[0]["password"] == "OLProgram"

    backups = list(backup_dir.glob("*_pre_import_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_name = con.execute("SELECT name FROM users").fetchone()[0]
    finally:
        con.close()
    assert backed_up_name == "Original User"


def test_import_validation_rejection_is_returned_without_replacing_data(
    monkeypatch, tmp_path, temp_db
):
    _seed_user(temp_db)
    temp_db.upload_values(
        [
            {
                "barcode": 101,
                "name": "Referenced Product",
                "price": 10,
                "category": "Drinks",
                "current_stock": 10,
                "initial_stock": 10,
            }
        ],
        "prods",
    )
    temp_db.upload_values(
        [
            {
                "barcode_user": 1000,
                "barcode_prod": 101,
                "timestamp": "2026-01-01 12:00:00",
            }
        ],
        "transactions",
    )
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    products_without_reference = _encoded_csv(
        PRODUCT_HEADER + "102,Other Product,12,Drinks,5,5\n"
    )

    result = _run_import(
        monkeypatch,
        [None, products_without_reference, None],
        table_name="prods",
    )

    assert result.error is None
    assert result.values[2] is True
    assert result.values[3][1] == [
        {
            "barcode": 101,
            "error": "Missing product referenced by 1 transaction(s)",
        }
    ]
    assert list(temp_db.prods["barcode"]) == ["101"]
    assert temp_db.settings.iloc[0]["password"] == "OLProgram"
    assert len(list(backup_dir.glob("*_pre_import_*.db"))) == 1


def test_malformed_upload_returns_five_fallback_outputs(
    monkeypatch,
    tmp_path,
    temp_db,
):
    _seed_user(temp_db)
    monkeypatch.setattr(
        main_page_callbacks,
        "BACKUP_DIR",
        str(tmp_path / "backups"),
    )

    result = _run_import(
        monkeypatch,
        ["data:text/csv;base64,%%%", None, None],
        table_name="users",
    )

    assert result.error is not None
    assert len(result.values) == 5
    assert list(temp_db.users["name"]) == ["Original User"]


def test_successful_import_result_closes_and_clears_bad_rows_modal():
    assert main_page_callbacks.open_bad_rows(True, [[], [], []]) == (
        False,
        [[], [], []],
    )


def test_barcode_export_builds_pdfs_in_memory(monkeypatch):
    calls = []

    def record_pdf(type, pdf_filename):
        assert isinstance(pdf_filename, io.BytesIO)
        calls.append(type)
        pdf_filename.write(f"%PDF-{type}".encode("ascii"))

    monkeypatch.setattr(main_page_callbacks, "generate_pdf", record_pdf)

    download = main_page_callbacks.export_barcodes.__wrapped__(1)

    assert calls == ["users", "prods", "multipliers"]
    assert download["filename"].startswith("barcodes_")
