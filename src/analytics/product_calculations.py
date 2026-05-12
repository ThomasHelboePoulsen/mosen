from src.database.data_connection import get_prods
from src.analytics.trans_calculations import get_currently_sold

def calculate_waste():
    prods = get_prods()
    waste = sum(
        [
            (
                (int(p["initial_stock"]) - int(p["current_stock"]))
                - get_currently_sold(p)
            )
            * float(p["price"])
            for _, p in prods.iterrows()
        ]
    )
    return int(waste)


def get_waste_table():
    prods = get_prods()
    waste = [
        {
            "Barcode": int(p["barcode"]),
            "Product": p["name"],
            "Amount Sold": get_currently_sold(p),
            "Waste": (
                n_waste := int(p["initial_stock"])
                - int(p["current_stock"])
                - get_currently_sold(p)
            ),
            "Total Price": n_waste * float(p["price"]),
        }
        for _, p in prods.iterrows()
    ]
    return waste
