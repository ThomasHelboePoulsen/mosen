
from pandas import DataFrame
from plotly import express as px
from src.database.data_connection import (
    get_prods,
    get_trans,
    get_users,
    upload_values,
    update_values,
    reset_all_tables,
    get_waste,
)

def filter_guest_users(transactions, users):
    users = users[users["is_guest"].astype(int) != 1]
    
    valid_barcodes = set(users["barcode"].astype(str))
    transactions = transactions[transactions["barcode_user"].astype(str).isin(valid_barcodes)]
    return transactions, users

def create_overview(plot_col, average=False):
    prods = get_prods()
    transactions = get_trans()
    users = get_users()
    transactions, users = filter_guest_users(transactions, users)
    
    if len(transactions) == 0:
        return px.bar()

    def translation(x, t_dict):
        try:
            ret = t_dict[str(x)]
        except:
            ret = "UNKNOWN"
        return ret

    if plot_col == "products":
        text = lambda x: f"{x} category"
        ranks = [text(cat) for cat in list(prods["category"].unique())]
        rank_dict = {
            str(row["barcode"]): text(row["category"]) for i, row in prods.iterrows()
        }
        transactions["rank"] = transactions["barcode_prod"].apply(
            translation, t_dict=rank_dict
        )

    else:
        text = lambda x: f"{x} {plot_col.lower()}"
        ranks = [text(rank) for rank in list(users[str(plot_col)].unique())]
        rank_dict = {
            str(row["barcode"]): text(row[str(plot_col)]) for i, row in users.iterrows()
        }

        transactions["rank"] = transactions["barcode_user"].apply(
            translation, t_dict=rank_dict
        )

    prod_dict = {str(row["barcode"]): row["name"] for i, row in prods.iterrows()}
    transactions["prod_names"] = transactions["barcode_prod"].apply(
        translation, t_dict=prod_dict
    )
    overview_df = [
        transactions[transactions["rank"] == rank].value_counts("prod_names").to_dict()
        for rank in ranks
    ]

    if average:
        if plot_col == "products":
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := int(
                                prods[prods["category"] == ranks[i][:-9]][
                                    "initial_stock"
                                ].values[0]
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
        else:
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := len(
                                users[
                                    users[str(plot_col)]
                                    == ranks[i][: -(len(plot_col) + 1)]
                                ]
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
    y = [
        prods[prods["barcode"] == str(p)]["name"].values[0]
        for p in transactions["barcode_prod"]
    ]
    return px.bar(overview_df, x=ranks, y=y)