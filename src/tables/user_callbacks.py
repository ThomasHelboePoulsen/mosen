import pandas as pd
from src.barcode import BarcodePartition, is_barcode
from dash import callback, Output, Input, State, html, ctx, ALL, no_update
from src.database.data_connection import db_transaction_raises, upload_values, get_users, get_trans
from src.container import Container
from src.database.data_connection import Database
from src.error_handler import callback_with_error_queue, Result


@callback(
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output({"type": "user_input", "index": "inp_barcode_user"}, "value"),
    Input("new_user_btn", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("cancel_user", "n_clicks"),
    prevent_initial_call=True,
)
def open_user_modal(new_user, confirm, cancel):
    trigger = ctx.triggered_id
    if trigger is None:
        return no_update, no_update

    try:
        table_data = Container.get(Database)._user_table.get()
        barcode = max(table_data["barcode"]) + 1
    except:
        barcode = 1000
    if trigger == "new_user_btn":
        return True, barcode
    elif trigger == "confirm_user":
        return False, no_update
    else:
        return False, no_update


@callback(
    Output("confirm_user", "disabled"),
    Input({"type": "user_input", "index": ALL}, "value"),
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
)
def enable_confirm(inps, invalid_barcode):
    if None not in inps and not invalid_barcode:
        return False
    return True


@callback_with_error_queue(2,
    Output("user_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Input("confirm_user", "n_clicks"),
    State({"type": "user_input", "index": ALL}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def add_row_callback(n_clicks, vals, edit_barcode):
    return add_row(n_clicks, vals, edit_barcode)

@db_transaction_raises
def add_row(n_clicks, vals, edit_barcode):
    db = Container.get(Database)
    table = db._user_table
    
    if n_clicks is None:
        return no_update, no_update
    if n_clicks > 0:
        data = table.get()
        
        if db.barcode_exists(edit_barcode, BarcodePartition.USER):
            barcode_mask = data["barcode"]== int(edit_barcode)
            if barcode_mask.any():
                data = data[~barcode_mask].copy()

        new_row = {col.name: val for col, val in zip(table.columns, vals)}        
        new_row["is_guest"] = 1 if new_row.get("is_guest") else 0

        data = pd.concat([data, pd.DataFrame([new_row])])
        success, bad_rows = db.try_upload_values(data, "users") 
        if not success:
             raise ValueError(f"Failed to upload user data. Bad rows: {bad_rows}")


    if is_barcode(edit_barcode, BarcodePartition.USER):
        trans = db._transaction_table.get()
        trans_mask = trans["barcode_user"]== int(edit_barcode)
        trans.loc[trans_mask, "barcode_user"] = int(vals[0])
        success, bad_rows = db.try_upload_values(trans, "transactions")
        if not success:
             raise ValueError(f"Failed to upload product data. Bad rows: {bad_rows}")


    return table.get().to_dict(orient="records"), None


@callback(
    Output({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def validate_barcode_user(value, edit_barcode):
    bars = [row["barcode"] for row in get_users().to_dict(orient="records")]
    bars.extend([row["barcode_user"] for row in get_trans().to_dict(orient="records")])
    if (
        value is None
        or not str(value).isdigit()
        or len(str(value)) < 4
        or (str(value) in set(bars) and str(value) != str(edit_barcode))
    ):
        return True
    return False
