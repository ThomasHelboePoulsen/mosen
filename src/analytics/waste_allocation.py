import math
from abc import ABC, abstractmethod
from fractions import Fraction

from src.analytics.product_calculations import (
    calculate_category_waste_cents,
    calculate_waste_cents,
)


class WasteAllocationStrategy(ABC):
    label: str

    @abstractmethod
    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        raise NotImplementedError

    @staticmethod
    def equal_split(total_waste_cents: int, barcodes: list[str]) -> dict[str, int]:
        if total_waste_cents <= 0 or not barcodes:
            return {barcode: 0 for barcode in barcodes}
        share_cents = math.ceil(total_waste_cents / len(barcodes) / 100) * 100
        return {barcode: share_cents for barcode in barcodes}


class EqualAllStrategy(WasteAllocationStrategy):
    label = "Equal all users"

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        barcodes = sorted(users["barcode"].astype(str).tolist())
        return self.equal_split(total_waste_cents, barcodes)


class EqualActiveStrategy(WasteAllocationStrategy):
    label = "Equal active users"

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        current_barcodes = set(users["barcode"].astype(str))
        transactions = db._transaction_table.get()
        active_barcodes = (
            set(transactions["barcode_user"].astype(str))
            if len(transactions)
            else set()
        )
        eligible = sorted(current_barcodes & active_barcodes)
        if not eligible:
            return EqualAllStrategy().allocate(db, total_waste_cents)
        allocations = {barcode: 0 for barcode in current_barcodes}
        allocations.update(self.equal_split(total_waste_cents, eligible))
        return allocations


class EqualCategoryPurchasersStrategy(WasteAllocationStrategy):
    label = "Equal category purchasers"

    @staticmethod
    def _round_up_to_whole_krone(amount: Fraction) -> int:
        if amount <= 0:
            return 0
        whole_kroner = (
            amount.numerator + amount.denominator * 100 - 1
        ) // (amount.denominator * 100)
        return whole_kroner * 100

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        current_barcodes = set(users["barcode"].astype(str))
        allocations = {
            barcode: Fraction(0) for barcode in current_barcodes
        }
        if total_waste_cents <= 0 or not current_barcodes:
            return {barcode: 0 for barcode in current_barcodes}

        products = db._product_table.get()
        transactions = db._transaction_table.get()
        category_waste = calculate_category_waste_cents(products, transactions)
        positive_waste = {
            category: waste
            for category, waste in category_waste.items()
            if waste > 0
        }
        total_positive_waste = sum(positive_waste.values())

        active_barcodes = (
            current_barcodes & set(transactions["barcode_user"].astype(str))
            if len(transactions)
            else set()
        )
        product_categories = {
            str(product["barcode"]): str(product["category"])
            for _, product in products.iterrows()
        }
        category_purchasers = {}
        for _, transaction in transactions.iterrows():
            category = product_categories.get(str(transaction["barcode_prod"]))
            barcode = str(transaction["barcode_user"])
            if category is not None and barcode in current_barcodes:
                category_purchasers.setdefault(category, set()).add(barcode)

        for category, waste_cents in positive_waste.items():
            category_budget = Fraction(
                total_waste_cents * waste_cents,
                total_positive_waste,
            )
            eligible = category_purchasers.get(category, set())
            if not eligible:
                eligible = active_barcodes or current_barcodes
            share = category_budget / len(eligible)
            for barcode in eligible:
                allocations[barcode] += share

        return {
            barcode: self._round_up_to_whole_krone(amount)
            for barcode, amount in allocations.items()
        }


STRATEGIES = {
    "equal_category_purchasers": EqualCategoryPurchasersStrategy(),
    "equal_active": EqualActiveStrategy(),
    "equal_all": EqualAllStrategy(),
}


def get_strategy_options() -> list[dict[str, str]]:
    return [
        {"label": strategy.label, "value": key}
        for key, strategy in STRATEGIES.items()
    ]


def allocate_waste(db) -> dict[str, int]:
    strategy_key = str(db.settings.iloc[0]["waste_strategy"])
    if strategy_key not in STRATEGIES:
        raise ValueError(f"Unknown waste strategy: {strategy_key}")

    total_waste_cents = calculate_waste_cents(
        db._product_table.get(),
        db._transaction_table.get(),
    )
    allocations = STRATEGIES[strategy_key].allocate(db, total_waste_cents)

    users = db._user_table.get()
    users["waste_cents"] = (
        users["barcode"].astype(str).map(allocations).fillna(0).astype(int)
    )
    db.upload_values_raises(users, "users")

    settings = db._settings_table.get()
    settings.loc[0, "waste_cents"] = total_waste_cents
    db.upload_values_raises(settings, "settings")

    allocated = int(users["waste_cents"].sum()) if len(users) else 0
    charged_users = int((users["waste_cents"] > 0).sum()) if len(users) else 0
    if charged_users and allocated < total_waste_cents:
        raise ValueError("Waste allocation did not cover the calculated waste")
    if charged_users and allocated - total_waste_cents >= charged_users * 100:
        raise ValueError("Waste allocation exceeded the allowed rounding overage")
    return allocations
