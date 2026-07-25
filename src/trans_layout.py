from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime
from src.components import get_barcode
from src.error_handler import callback_with_error_queue,Result
from src.barcode import BarcodePartition
from src.container import Container
from src.database.data_connection import (
    Database,
    db_transaction_raises,
    db_transaction_result,
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
    update_current_trans,
    reset_current_trans,
    get_show_bill,
    get_waste_cents,
)
from src.analytics.bill_preview import get_preview_user_waste_cents
from src.analytics.bar_chart_format import format_count_bar_chart
from src.skins import (
    checkout_theme_class,
    get_skin_by_barcode,
    get_user_skin_key,
)


def _format_checkout_history_chart(fig):
    """Keep the purchase history readable without hiding the active skin."""

    fig = format_count_bar_chart(fig, show_x_tick_labels=False)
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        legend_title_text=None,
        font_color="#172117",
    )
    fig.update_xaxes(gridcolor="rgba(23, 33, 23, 0.16)")
    fig.update_yaxes(gridcolor="rgba(23, 33, 23, 0.16)")
    return fig


def trans_modal():
    modal = dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(html.H1(id="new_trans_user")),
                        ]
                    ),
                    width=12,
                ),
                close_button=False,
            ),
            dbc.ModalBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [html.H1("Products: ")], id="show_current_prods"
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        dbc.Row(
                                            dbc.Col(
                                                children=dcc.Graph(
                                                    id="trans_graph",
                                                    config={"displayModeBar": False},
                                                    # style={"maxHeight": "350px"},
                                                ),
                                                id="prod_barchart",
                                            ),
                                        ),
                                    ],
                                    className="show_box",
                                ),
                                width=7,
                            ),
                        ]
                    ),
                    dbc.Row(
                        dbc.Input(
                            placeholder="Barcode",
                            id="prod_barcode",
                            autoFocus=True,
                        ),
                        align="end",
                    ),
                ],
            ),
        ],
        is_open=False,
        id="new_trans_modal",
        fullscreen=True,
        keyboard=False,
        className=checkout_theme_class(None),
    )
    return modal


@callback_with_error_queue(1,
    Output("trans_graph", "figure"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
)
def get_transactions(trigger, barcode):
    if trigger is None:
        return no_update, no_update
    users = get_users()
    barcode = get_barcode(barcode)
    user_barcodes = list(map(str, users["barcode"]))
    if not (str(barcode) in user_barcodes):
        raise ValueError("User not found")
    transactions = get_trans()
    user_trans = transactions[transactions["barcode_user"] == str(barcode)].copy()
    if len(user_trans) == 0:
        return _format_checkout_history_chart(px.bar([{}]))

    prods = get_prods()
    prod_names = {str(p["barcode"]): p["name"] for _, p in prods.iterrows()}
    user_trans["name"] = user_trans["barcode_prod"].map(
        lambda value: prod_names.get(str(value))
    )
    user_trans = user_trans[user_trans["name"].notna()]
    trans_data = [user_trans["name"].value_counts().to_dict()]
    return _format_checkout_history_chart(px.bar(trans_data))


@callback_with_error_queue(4,
    Output("new_trans_modal", "is_open"),
    Output("new_trans_inp", "value"),
    Output("prod_barcode", "value", allow_duplicate=True),
    Output("new_trans_modal", "className"),
    Input("new_trans_inp", "n_submit"),
    Input("prod_barcode", "n_submit"),
    State("new_trans_inp", "value"),
    State("prod_barcode", "value"),
)
def open_trans_modal(trigger_open, trigger_close, barcode_open, barcode_close):
    db = Container.get(Database)
    clear_barcode_open = (
        no_update,
        "",
        no_update,
        checkout_theme_class(None),
    )
    clear_barcode_close = (no_update, no_update, "", no_update)
    barcode_open = get_barcode(barcode_open)
    if barcode_open == "bad barcode":
        return Result(clear_barcode_open, ValueError("Invalid barcode"))
    barcode_close = get_barcode(barcode_close)
    if barcode_close == "bad barcode":
        return Result(clear_barcode_close, ValueError("Invalid barcode"))
    
    trigger = ctx.triggered_id
    if trigger == "new_trans_inp":
        users = db.get_table("users").get()
        user_barcodes = list(users["barcode"])
        if len(user_barcodes) < 1:
            return Result(clear_barcode_open, ValueError("No users exist"))
        if barcode_open is None or not barcode_open.isdecimal():
            return Result(clear_barcode_open, ValueError("Empty barcode"))
        if int(barcode_open) in user_barcodes:
            user = users[users["barcode"] == int(barcode_open)].iloc[0]
            if int(user.get("paid_cents", 0)) > 0:
                return Result(clear_barcode_open, ValueError("User has already paid"))
            reset_current_trans()
            skin_key = get_user_skin_key(
                user["barcode"],
                db._transaction_table.get(),
            )
            return True, no_update, "", checkout_theme_class(skin_key)
        return clear_barcode_open #I couldn't provoke this branch when testing
    
    elif trigger == "prod_barcode" and strings_map_to_same_number(barcode_close,barcode_open):
        checkout_cart_to(barcode_close, db)
        return False, "", no_update, no_update

    return no_update, no_update, no_update, no_update

@db_transaction_raises
def checkout_cart_to(user_barcode, db:Database):
    if not db.barcode_exists(user_barcode, BarcodePartition.USER):
        raise ValueError(f"User not found: {user_barcode}")
    users = db._user_table.get()
    user = users[users["barcode"] == int(user_barcode)]
    if len(user) and int(user.iloc[0].get("paid_cents", 0)) > 0:
        raise ValueError(f"User has already paid: {user_barcode}")
    current = db._temporary_table.get()
    if current.empty:
        return

    new_rows = pd.DataFrame(
        [
            {
                "barcode_user": user_barcode,
                "barcode_prod": row["barcode_prod"],
                "timestamp": str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            }
            for _, row in current.iterrows()
        ]
    )
    add_result, bad_rows = db._transaction_table.append(new_rows)
    if not add_result == "success":
        raise ValueError(f"Failed to add transactions due to the following bad rows: {bad_rows}")

    db._temporary_table.set([])


def strings_map_to_same_number(s1,s2):
    return s1.isdecimal() and s2.isdecimal() and int(s1) == int(s2)

@callback_with_error_queue(2,
    Output("show_current_prods", "children"),
    Output("prod_barcode", "value"),
    Input("prod_barcode", "n_submit"),
    State("prod_barcode", "value"),
    State("new_trans_inp", "value"),
)
@db_transaction_result(fallback_values=(no_update, ""))
def new_trans(trigger, _barcode, user_barcode):

    prods = get_prods()
    current = get_current_trans()
    barcode = get_barcode(_barcode)
    if (not str(barcode).isdigit()) or len(str(barcode)) < 1:
        raise ValueError(f"Invalid barcode: {_barcode}")
    user_barcode = get_barcode(user_barcode)
    if barcode == user_barcode:
        return ( [html.H1("Products: ")], "" )
    elif int(barcode) == 0:
        if len(current) == 0:
            raise ValueError("You can't remove products before adding any")
        last_barcode = current.iloc[len(current) - 1]["barcode_prod"]
        indecies = current[current["barcode_prod"] == str(last_barcode)].index
        current.drop(indecies, inplace=True)
    elif len(barcode) < 3:
        if len(current) == 0:
            raise ValueError("You can't use a multiplier without choosing product")
        last_barcode = current.iloc[len(current) - 1]["barcode_prod"]
        if get_skin_by_barcode(last_barcode) is not None:
            raise ValueError("Skins cannot be multiplied")
        current_amount = len(current[current["barcode_prod"] == str(last_barcode)])
        addition = int(barcode) if current_amount > 1 else int(barcode) - 1
        for _ in range(addition):
            last = current.iloc[len(current) - 1]
            data = [
                {col: last.values[i] for i, col in enumerate(list(current.columns))}
            ]
            current = pd.concat([current, pd.DataFrame(data)], ignore_index=True)
    elif barcode not in list(prods["barcode"].astype(str)):
        not_found = "Product" if int(barcode) < 1000 else "User"
        raise ValueError(f"{not_found} not found: {barcode}")
    else:
        product = prods[prods["barcode"].astype(str) == barcode].iloc[0]
        name = str(product["name"])
        if get_skin_by_barcode(barcode) is not None:
            current = current[
                current["barcode_prod"].map(get_skin_by_barcode).isna()
            ].copy()
        new_transaction = pd.DataFrame(
            [{"barcode_prod": barcode, "name": name}]
        )
        current = pd.concat([current, new_transaction], ignore_index=True)

    display_text = [html.H1("Products: ")]
    for current_barcode in current["barcode_prod"].unique():
        prod_name = str(
            current[current["barcode_prod"] == current_barcode]["name"].values[0]
        )
        current_amount = int(len(current[current["barcode_prod"] == current_barcode]))
        display_text.append(html.H2(f"{current_amount}x: {prod_name}"))

    update_current_trans(current)

    return display_text, ""


@callback(
    Output("new_trans_user", "children"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
)
def show_balance(trigger, user_id):
    if trigger is None:
        return no_update
    users = get_users()
    user_id = get_barcode(user_id)
    try:
        user_row = users[users["barcode"] == str(user_id)].iloc[0]
        user = str(user_row["name"])
    except:
        return no_update

    if not get_show_bill():
        return str(user)
    else:
        trans = get_trans()
        user_trans = trans[trans["barcode_user"] == str(user_id)].copy()
        prods = get_prods()
        price_dict = {str(p["barcode"]): p["price"] for _, p in prods.iterrows()}
        user_trans["price"] = user_trans["barcode_prod"].map(
            lambda x: price_dict.get(str(x), 0)
        )

        user_balance = sum(map(float, user_trans["price"]))
        user_waste = get_preview_user_waste_cents(
            user_row,
            get_waste_cents(),
            len(users),
        ) / 100
        return f"{user} - Current bill is approximately: {max(0, round(user_balance + user_waste))}"
