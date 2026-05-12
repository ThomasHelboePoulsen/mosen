import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL, no_update
from src.data_connection import upload_values, get_users, get_trans
from src.container import Container
from src.data_connection import Database
    


def init():
    #TODO: Figure out what was supposed to happen here
    pass


@callback(
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output({"type": "user_input", "index": "inp_barcode_user"}, "value"),
    Input("new_user_btn", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("cancel_user", "n_clicks"),
    State("user_table", "data"),
    prevent_initial_call=True,
)
def open_user_modal(new_user, confirm, cancel, data):
    trigger = ctx.triggered_id
    if trigger is None:
        return no_update, no_update

    try:
        barcode = int(max(pd.DataFrame(data)["barcode"])) + 1
    except KeyError:
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


@callback(
    Output("user_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Input("confirm_user", "n_clicks"),
    State({"type": "user_input", "index": ALL}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def add_row(n_clicks, vals, edit_barcode):
    db = Container.get(Database)
    table = db._user_table
    
    if n_clicks is None:
        return no_update, no_update
    if n_clicks > 0:
        data = table.get()
        
        if edit_barcode is not None:
            barcode_mask = data["barcode"].astype(str) == str(edit_barcode)
            if barcode_mask.any():
                data = data[~barcode_mask].copy()

        new_row = {col.name: val for col, val in zip(table.columns, vals)}        
        new_row["is_guest"] = 1 if new_row.get("is_guest") else 0
        
        all_data_records = data.to_dict('records')
        if not table.is_valid_single(new_row, all_data_records):
            return no_update, no_update
        
        data = pd.concat([data, pd.DataFrame([new_row])])
        upload_values(data, "users")

    if edit_barcode is not None and int(edit_barcode) > 999:
        trans = get_trans()
        trans_mask = trans["barcode_user"].astype(str) == str(edit_barcode)
        trans.loc[trans_mask, "barcode_user"] = int(vals[0])
        upload_values(trans, "transactions")

    return data.to_dict(orient="records"), None


@callback(
    Output({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "value"),
    State("edit_input", "value"),
    prevent_initial_callback=True,
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
