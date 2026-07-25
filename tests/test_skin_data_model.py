from io import StringIO

import pandas as pd
import pytest

from src.analytics.product_calculations import calculate_waste_cents, get_waste_table
from src.main_page_callbacks import (
    download_product_template,
    get_starter_product_template,
)
from src.modals import update_stock_modal
from src.skins import SKINS
from src.tables.prod_callbacks import confirm_new_stock


def product(barcode=101, **overrides):
    row = {
        "barcode": barcode,
        "name": "Cola",
        "price": 10,
        "category": "Drinks",
        "current_stock": 5,
        "initial_stock": 10,
    }
    row.update(overrides)
    return row


def skin_product(barcode=900, **overrides):
    skin = next(skin for skin in SKINS.values() if skin.barcode == barcode)
    row = {
        "barcode": barcode,
        "name": skin.name,
        "price": skin.starter_price,
        "category": "Skins",
        "current_stock": 0,
        "initial_stock": 0,
    }
    row.update(overrides)
    return row


def user():
    return {
        "barcode": 1000,
        "name": "Ada",
        "rank": "Student",
        "team": "A",
    }


def component_ids(component):
    result = []
    component_id = getattr(component, "id", None)
    if component_id is not None:
        result.append(component_id)
    children = getattr(component, "children", None)
    if children is None:
        return result
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        result.extend(component_ids(child))
    return result


@pytest.mark.parametrize(
    ("barcode", "field", "value"),
    [
        (900, "current_stock", 1),
        (901, "initial_stock", 1),
        (902, "current_stock", 0.5),
        (903, "initial_stock", -0.5),
    ],
)
def test_reserved_skin_barcodes_require_exactly_zero_stock(
    temp_db,
    barcode,
    field,
    value,
):
    row = skin_product(barcode, **{field: value})

    result, bad_rows = temp_db._product_table.set([row])

    assert result == "prods"
    assert bad_rows == [row]
    assert temp_db._product_table.get().empty


def test_default_reset_product_must_be_free(temp_db):
    charged_reset = skin_product(903, price=0.01)

    result, bad_rows = temp_db._product_table.set([charged_reset])

    assert result == "prods"
    assert bad_rows == [charged_reset]

    free_reset = skin_product(903, price=0)
    result, bad_rows = temp_db._product_table.set([free_reset])

    assert result == "success"
    assert bad_rows == []
    assert temp_db._product_table.get().iloc[0]["price"] == 0


@pytest.mark.parametrize("price", ["", "not a price", -1, float("nan"), float("inf")])
def test_paid_skin_price_must_be_finite_and_nonnegative(temp_db, price):
    row = skin_product(900, price=price)

    result, bad_rows = temp_db._product_table.set([row])

    assert result == "prods"
    assert bad_rows == [row]


def test_stock_count_excludes_reserved_skin_products(temp_db):
    temp_db.upload_values(
        pd.DataFrame([product(current_stock=5), skin_product(900)]),
        "prods",
    )

    stock_inputs = [
        component_id
        for component_id in component_ids(update_stock_modal())
        if isinstance(component_id, dict)
        and component_id.get("type") == "new_stock_inp"
    ]
    confirm_new_stock([4])

    products = temp_db._product_table.get().set_index("barcode")
    assert len(stock_inputs) == 1
    assert products.loc[101, "current_stock"] == 4
    assert products.loc[900, "current_stock"] == 0


def test_skin_revenue_credits_physical_waste_at_current_price(temp_db):
    temp_db.upload_values(pd.DataFrame([user()]), "users")
    temp_db.upload_values(
        pd.DataFrame([product(), skin_product(900, price=2)]),
        "prods",
    )
    result, bad_rows = temp_db._transaction_table.append(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": barcode,
                    "timestamp": f"2026-01-01 10:00:0{index}",
                }
                for index, barcode in enumerate([101, 101, 900, 900])
            ]
        )
    )
    assert result == "success"
    assert bad_rows == []

    assert calculate_waste_cents() == 2600
    assert [row["Barcode"] for row in get_waste_table()] == [101]

    products = temp_db._product_table.get()
    products.loc[products["barcode"] == 900, "price"] = 5
    temp_db.upload_values_raises(products, "prods")

    assert calculate_waste_cents() == 2000


def test_starter_template_matches_registry_and_download(temp_db):
    generated_template = get_starter_product_template()
    result, bad_rows = temp_db._product_table.set(generated_template)

    assert result == "success"
    assert bad_rows == []
    assert list(generated_template.columns) == [
        "barcode",
        "name",
        "price",
        "category",
        "current_stock",
        "initial_stock",
    ]
    assert set(generated_template["barcode"]) == {
        skin.barcode for skin in SKINS.values()
    }
    assert (generated_template[["current_stock", "initial_stock"]] == 0).all().all()
    assert generated_template.set_index("barcode").loc[903, "price"] == 0

    download = download_product_template(1)
    downloaded_template = pd.read_csv(StringIO(download["content"]))
    pd.testing.assert_frame_equal(
        downloaded_template,
        generated_template,
        check_dtype=False,
    )
