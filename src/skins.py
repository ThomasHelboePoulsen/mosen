"""Fixed checkout skin registry and safe CSS-class selection."""

from dataclasses import dataclass
from math import isfinite

from src.barcode import RESERVED_SKIN_BARCODES


DEFAULT_SKIN_KEY = "default"


@dataclass(frozen=True)
class SkinDefinition:
    """Display metadata for one program-owned checkout skin."""

    key: str
    barcode: int
    name: str
    description: str
    starter_price: float


SKINS = {
    "default": SkinDefinition(
        key="default",
        barcode=903,
        name="Mosemaskinen",
        description="The familiar, no-frills checkout look.",
        starter_price=0,
    ),
    "swamp": SkinDefinition(
        key="swamp",
        barcode=900,
        name="Deep Swamp",
        description="Reeds, bubbles, and deep bog greens.",
        starter_price=2,
    ),
    "retro": SkinDefinition(
        key="retro",
        barcode=901,
        name="Bog Terminal",
        description="Amber phosphor and chunky terminal panels.",
        starter_price=2,
    ),
    "neon": SkinDefinition(
        key="neon",
        barcode=902,
        name="Neon Bog",
        description="Electric cyan and magenta after dark.",
        starter_price=3,
    ),
}

_SKINS_BY_BARCODE = {str(skin.barcode): skin for skin in SKINS.values()}
if {int(barcode) for barcode in _SKINS_BY_BARCODE} != RESERVED_SKIN_BARCODES:
    raise RuntimeError("The skin registry must match the reserved skin barcodes.")


def normalize_skin_key(skin_key: object | None) -> str:
    """Return a registered key, falling back safely to the default skin."""

    if isinstance(skin_key, str):
        normalized = skin_key.strip().lower()
        if normalized in SKINS:
            return normalized
    return DEFAULT_SKIN_KEY


def get_skin(skin_key: object | None) -> SkinDefinition:
    """Return metadata for ``skin_key`` or the default skin."""

    return SKINS[normalize_skin_key(skin_key)]


def get_skin_by_barcode(barcode: object) -> SkinDefinition | None:
    """Return the fixed skin assigned to ``barcode``, if any."""

    try:
        return _SKINS_BY_BARCODE.get(str(int(barcode)))
    except (TypeError, ValueError):
        return None


def skin_product_mask(products):
    """Return a boolean mask selecting program-owned skin products."""

    return products["barcode"].astype(str).isin(_SKINS_BY_BARCODE)


def without_skin_products(products):
    """Return only physical products from a product DataFrame."""

    return products.loc[~skin_product_mask(products)]


def get_user_skin_key(user_barcode, transactions) -> str:
    """Return the user's most recently purchased skin, or the default."""

    user_transactions = transactions[
        transactions["barcode_user"].astype(str) == str(int(user_barcode))
    ]
    for product_barcode in reversed(user_transactions["barcode_prod"].tolist()):
        skin = get_skin_by_barcode(product_barcode)
        if skin is not None:
            return skin.key
    return DEFAULT_SKIN_KEY


def is_valid_skin_product(row: dict) -> bool:
    """Validate the product-row invariants owned by fixed checkout skins."""

    skin = get_skin_by_barcode(row.get("barcode"))
    if skin is None:
        return True

    try:
        price = float(row["price"])
        has_zero_stock = (
            float(row["current_stock"]) == 0
            and float(row["initial_stock"]) == 0
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    return (
        has_zero_stock
        and isfinite(price)
        and price >= 0
        and (skin.key != DEFAULT_SKIN_KEY or price == 0)
    )


def get_starter_skin_products() -> list[dict]:
    """Return the fixed skin rows used by the downloadable product template."""

    return [
        {
            "barcode": skin.barcode,
            "name": skin.name if skin.key != DEFAULT_SKIN_KEY else "Default checkout",
            "price": skin.starter_price,
            "category": "Skins",
            "current_stock": 0,
            "initial_stock": 0,
        }
        for skin in SKINS.values()
    ]


def checkout_theme_class(skin_key: object | None) -> str:
    """Build a safe modal class, leaving the default checkout untouched."""

    normalized = normalize_skin_key(skin_key)
    if normalized == DEFAULT_SKIN_KEY:
        return ""
    return f"checkout-theme theme--{normalized}"
