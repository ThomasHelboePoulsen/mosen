import base64
import sqlite3
import types

from dash import no_update

from src import main_page_callbacks
from src.database.data_connection import Database
from src.container import Container


def _encoded_csv(csv):
    return "data:text/csv;base64," + base64.b64encode(
        csv.encode("utf-8")
    ).decode("ascii")


def test_payment_modal_stays_closed_when_economy_tab_renders(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="export_payments_btn"),
    )

    # Act
    result = main_page_callbacks.control_payments_modal(
        None, None, 0, "Up", 0, []
    )

    # Assert
    assert result == (no_update, no_update, no_update)


def test_successful_import_commits_settings_and_data_after_backup(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended success path: backup first, then commit settings/import."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id={"index": "users", "type": "database_upload"}),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    csv = "barcode,name,rank,team\n1001,Imported User,Member,B\n"
    encoded_csv = _encoded_csv(csv)

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        None,
        True,
        [encoded_csv, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_category_purchasers",
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[0] is True
    assert result.values[2] is False
    assert Container.get(Database).users.iloc[0]["name"] == "Imported User"
    assert Container.get(Database).settings.iloc[0]["password"] == "pw"

    backups = list(backup_dir.glob("*_pre_import_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_user = con.execute("SELECT name FROM users").fetchone()[0]
    finally:
        con.close()
    assert backed_up_user == "Original User"


def test_non_upload_settings_trigger_does_not_reimport_stale_upload(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended trigger behavior: upload contents are used only on upload."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_new_password"),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    stale_upload = _encoded_csv("barcode,name,rank,team\n1001,Imported User,Member,B\n")

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        1,
        True,
        [stale_upload, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_category_purchasers",
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[-1] is True
    assert Container.get(Database).users.iloc[0]["name"] == "Original User"
    assert not backup_dir.exists()


def test_failed_import_rolls_back_changes_but_keeps_pre_import_backup(
    monkeypatch, tmp_path, temp_db
):
    """Document the intended failure path: rollback DB changes, keep the safety copy."""
    # Arrange
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id={"index": "users", "type": "database_upload"}),
    )
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Original User",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    invalid_upload = _encoded_csv("barcode,name,rank,team\n999,Bad User,Member,B\n")

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        None,
        False,
        [invalid_upload, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_all",
        "pw",
    )

    # Assert
    assert result.error is None
    assert result.values[2] is True
    assert Container.get(Database).users.iloc[0]["name"] == "Original User"
    assert Container.get(Database).settings.iloc[0]["password"] == "OLProgram"
    assert Container.get(Database).settings.iloc[0]["waste_strategy"] == (
        "equal_category_purchasers"
    )

    backups = list(backup_dir.glob("*_pre_import_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_user = con.execute("SELECT name FROM users").fetchone()[0]
    finally:
        con.close()
    assert backed_up_user == "Original User"
