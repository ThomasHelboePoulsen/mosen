import pandas as pd
from uuid import uuid4
from datetime import datetime
from dash import callback, Output, Input, State, html, ctx, ALL, MATCH, no_update
from src.barcode import BarcodePartition, is_barcode
from src.database.data_connection import (
    get_prods,
    get_trans,
    db_transaction_raises,
    update_values,
)
from src.analytics.waste_allocation import allocate_waste
from src.container import Container
from src.database.data_connection import Database
from src.error_handler import callback_with_error_queue, Result

PRODUCT_FORM_COLUMNS = ["barcode", "name", "price", "category", "initial_stock"]


@callback(
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"type": "prod_input", "index": ALL}, "value", allow_duplicate=True),
    Output("edit_input", "value", allow_duplicate=True),
    Input("new_prod_btn", "n_clicks"),
    Input("cancel_prod", "n_clicks"),
    Input("new_prod_modal", "is_open"),
    prevent_initial_call=True,
)
def open_prod_modal(new_prod, cancel, is_open):
    trigger = ctx.triggered_id
    if trigger == "new_prod_btn" and new_prod:
        table_data = Container.get(Database)._product_table.get()
        barcode = int(table_data["barcode"].max()) + 1 if not table_data.empty else 101
        return True, [barcode, None, None, None, None], None
    if trigger == "cancel_prod" and cancel:
        return False, [no_update] * 5, None
    if trigger == "new_prod_modal" and is_open is False:
        return no_update, [no_update] * 5, None
    return no_update, [no_update] * 5, no_update


@callback(
    Output("confirm_prod", "disabled"),
    Input({"type": "prod_input", "index": ALL}, "value"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
)
def enable_confirm(inps, invalid_barcode):
    if None not in inps and not invalid_barcode:
        return False
    return True


@db_transaction_raises
def add_row(vals, edit_barcode) -> list[dict]:
    """Add or edit a product and return the updated table. Invalid data raises."""
    db = Container.get(Database)
    table = db._product_table
    data = table.get()

    new_row = dict(zip(PRODUCT_FORM_COLUMNS, vals))
    new_row["current_stock"] = new_row["initial_stock"]
    if db.barcode_exists(edit_barcode, BarcodePartition.PRODUCT):
        barcode_mask = data["barcode"] == int(edit_barcode)
        new_row["current_stock"] = int(data.loc[barcode_mask, "current_stock"].iloc[0])
        data = data[~barcode_mask].copy()

    data = pd.concat([data, pd.DataFrame([new_row])])
    db.upload_values_raises(data, "prods")

    if is_barcode(edit_barcode, BarcodePartition.PRODUCT):
        trans = db.get_table("transactions").get()
        trans.loc[trans["barcode_prod"] == int(edit_barcode), "barcode_prod"] = int(
            vals[0]
        )
        db.upload_values_raises(trans, "transactions")

    return table.get().to_dict(orient="records")


@callback_with_error_queue(
    4,
    Output("prod_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output("form_save_revision", "data", allow_duplicate=True),
    Input("confirm_prod", "n_clicks"),
    State({"type": "prod_input", "index": ALL}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def add_row_callback(n_clicks, vals, edit_barcode):
    if not n_clicks:
        return no_update, no_update, no_update, no_update
    rows, = add_row(vals, edit_barcode)
    return rows, None, False, uuid4().hex


@callback(
    Output({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def validate_barcode_prod(value, edit_barcode):
    bars = [row["barcode"] for row in get_prods().to_dict(orient="records")]
    bars.extend([row["barcode_prod"] for row in get_trans().to_dict(orient="records")])
    if str(value) != str(edit_barcode) and (
        str(value) in set(bars)
        or value is None
        or type(value) != int
        or len(str(value)) != 3
    ):
        return True
    return False


@callback_with_error_queue(1,
    Output("new_stock_modal", "is_open"),
    Input("open_update_stock", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "new_stock_inp", "index": ALL}, "value"),
)
def open_stock(trigger_open, trigger_close, inps):
    trigger = ctx.triggered_id
    if trigger == "open_update_stock" and trigger_open:
        return True
    if trigger == "confirm_new_stock" and trigger_close:
        try:
            confirm_new_stock(inps)
            return False
        except Exception as e:
            #close on error, as clicking the button will do that anyway...
            #can be fixed by changing update_settings_layout to triggero on succesful db changes instead of button presses.
            return Result(False, error=e) 
    return no_update

@db_transaction_raises
def confirm_new_stock(inps):
    db = Container.get(Database)
    prods = db.get_table("prods").get()
    if None in inps or any(int(a) < 0 for a in inps): #While current stock can become negative, if someone scans too much, i don't think you would ever set it as negative.
        raise ValueError("You cannot set a negative stock value or leave it empty.")
    prods["current_stock"] = [int(val) for val in list(inps)]
    db.upload_values_raises(prods, "prods")
    allocate_waste(db)
    update_values(last_stock_update_at=datetime.now().isoformat(timespec="seconds"))
