import pandas as pd
import pytest

from src.database.import_validation import validate_import


USER_COLUMNS = [
    "barcode",
    "name",
    "rank",
    "team",
    "is_guest",
    "waste_cents",
    "paid_cents",
]
PRODUCT_COLUMNS = [
    "barcode",
    "name",
    "price",
    "category",
    "current_stock",
    "initial_stock",
]


def _user(barcode=1000, name="User"):
    return {
        "barcode": barcode,
        "name": name,
        "rank": "Member",
        "team": "A",
        "is_guest": 0,
        "waste_cents": -1,
        "paid_cents": 0,
    }


def _product(barcode=101, name="Product"):
    return {
        "barcode": barcode,
        "name": name,
        "price": 10,
        "category": "Drinks",
        "current_stock": 10,
        "initial_stock": 10,
    }


def _seed_transaction(db):
    db.upload_values([_user()], "users")
    db.upload_values([_product()], "prods")
    db.upload_values(
        [
            {
                "barcode_user": 1000,
                "barcode_prod": 101,
                "timestamp": "2026-01-01 12:00:00",
            }
        ],
        "transactions",
    )


def test_initial_import_may_be_abbreviated_but_replacement_requires_exact_headers(
    temp_db,
):
    abbreviated = pd.DataFrame(
        [
            {
                "barcode": 1000,
                "name": "User",
                "rank": "Member",
                "team": "A",
            }
        ]
    )

    assert validate_import(temp_db, "users", abbreviated) == []
    success, _ = temp_db.try_upload_values(abbreviated, "users")
    assert success

    errors = validate_import(temp_db, "users", abbreviated)
    complete = pd.DataFrame([_user(name="Updated User")], columns=USER_COLUMNS)

    assert errors == [
        {
            "error": (
                "Replacement imports must contain exactly these columns: "
                "barcode, name, rank, team, is_guest, waste_cents, paid_cents"
            )
        }
    ]
    assert validate_import(temp_db, "users", complete) == []


@pytest.mark.parametrize(
    "columns",
    [
        ["barcode", "name", "rank"],
        ["barcode", "name", "rank", "team", "unknown"],
    ],
)
def test_header_only_initial_import_requires_known_and_required_headers(
    temp_db,
    columns,
):
    errors = validate_import(
        temp_db,
        "users",
        pd.DataFrame(columns=columns),
    )

    assert len(errors) == 1
    assert "Initial imports must include the required columns" in errors[0][
        "error"
    ]
    assert "barcode, name, rank, team" in errors[0]["error"]


def test_full_header_only_import_can_clear_an_unreferenced_table(temp_db):
    temp_db.upload_values([_user()], "users")
    empty_import = pd.DataFrame(columns=USER_COLUMNS)

    assert validate_import(temp_db, "users", empty_import) == []
    success, bad_rows = temp_db.try_upload_values(empty_import, "users")

    assert success
    assert bad_rows == []
    assert temp_db.users.empty


@pytest.mark.parametrize(
    ("table_name", "candidate", "expected"),
    [
        (
            "users",
            pd.DataFrame([_user(1001, "Other User")], columns=USER_COLUMNS),
            {
                "barcode": 1000,
                "error": "Missing user referenced by 1 transaction(s)",
            },
        ),
        (
            "prods",
            pd.DataFrame(
                [_product(102, "Other Product")], columns=PRODUCT_COLUMNS
            ),
            {
                "barcode": 101,
                "error": "Missing product referenced by 1 transaction(s)",
            },
        ),
    ],
)
def test_replacement_cannot_remove_referenced_rows(
    temp_db, table_name, candidate, expected
):
    _seed_transaction(temp_db)

    assert validate_import(temp_db, table_name, candidate) == [expected]


def test_rows_can_be_removed_after_their_transactions_are_removed(temp_db):
    _seed_transaction(temp_db)
    temp_db.upload_values([], "transactions")
    empty_users = pd.DataFrame(columns=USER_COLUMNS)
    empty_products = pd.DataFrame(columns=PRODUCT_COLUMNS)

    assert validate_import(temp_db, "users", empty_users) == []
    assert validate_import(temp_db, "prods", empty_products) == []
