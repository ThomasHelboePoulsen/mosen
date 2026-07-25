from pathlib import Path

from src.barcode import BarcodePartition, RESERVED_SKIN_BARCODES, is_barcode
from src.skins import (
    SKINS,
    checkout_theme_class,
    get_skin,
)


PROJECT_ROOT = Path(__file__).parents[1]


def test_skin_registry_assets_and_css_classes_exist():
    styling = (PROJECT_ROOT / "assets" / "styling.css").read_text(encoding="utf-8")

    assert set(SKINS) == {"default", "swamp", "retro", "neon"}
    assert {skin.barcode for skin in SKINS.values()} == RESERVED_SKIN_BARCODES
    for skin in SKINS.values():
        if skin.key != "default":
            assert (PROJECT_ROOT / "assets" / f"skin-{skin.key}.svg").is_file()
            assert f".checkout-theme.theme--{skin.key}" in styling
            assert f'content: "{skin.name}"' in styling


def test_unknown_skin_falls_back_without_exposing_input_as_css():
    unknown_key = 'neon\" onclick=\"bad'

    assert get_skin(unknown_key).key == "default"
    assert checkout_theme_class(unknown_key) == ""
    assert unknown_key not in checkout_theme_class(unknown_key)


def test_default_skin_restores_the_unmodified_checkout_class():
    assert checkout_theme_class(None) == ""
    assert checkout_theme_class("default") == ""


def test_registry_contains_the_product_skin_keys():
    assert list(SKINS) == ["default", "swamp", "retro", "neon"]


def test_reserved_skin_barcodes_remain_in_the_product_partition():
    assert all(
        is_barcode(barcode, BarcodePartition.PRODUCT)
        for barcode in RESERVED_SKIN_BARCODES
    )
