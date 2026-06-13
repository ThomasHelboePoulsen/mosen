from dash import Output, Input, State, callback, ctx, no_update, html, ALL, MATCH, dcc
import pandas as pd
import plotly.express as px
from src.database.data_connection import (
    TransactionResult,
    db_transaction_raises,
    db_transaction_result,
    get_prods,
    get_trans,
    get_users,
    upload_values,
    update_values,
    reset_all_tables,
    get_waste,
)
from src.analytics.trans_calculations import get_income
from src.analytics.waste_allocation import allocate_waste
from src.barcode_generator import generate_pdf
from src.error_handler import append_error, callback_with_error_queue
from src.container import Container
from src.database.data_connection import Database
from src.analytics.overview_plot import create_overview

import base64
import io
import shutil
import os
import zipfile
import builtins
from datetime import datetime


@callback(
    Output("overview_graph", "figure"),
    Input("new_trans_modal", "is_open"),
    Input("graph_selection", "value"),
    Input("graph_average", "value"),
)
def update_overview_graph(trans_modal_open, graph_col, average):
    if not (ctx.triggered_id is not None and trans_modal_open == False):
        return no_update

    return create_overview(graph_col, average)


@callback_with_error_queue(5,
    Output("update_settings", "data"),
    Output("bad_password_alert", "is_open"),
    Output("bad_data_alert", "is_open"),
    Output({"index": ALL, "type": "bad_rows"}, "data"),
    Output("new_password_alert", "is_open"),
    Input("confirm_new_password", "n_clicks"),
    Input("display_bill_switch", "value"),
    Input({"index": ALL, "type": "database_upload"}, "contents"),
    Input({"index": ALL, "type": "database_upload"}, "id"),
    Input("waste_strategy", "value"),
    State("settings_password", "value"),
)
@db_transaction_result
def update_settings(pass_trigger, show_bill, db_tables, table_ids, waste_strategy, password):
    if (trigger := ctx.triggered_id) is None:
        return None, no_update, no_update, [no_update] * 3, no_update
    open_warning_password = False
    if password is None or len(password) == 0:
        open_warning_password = True
        password = "OLProgram"
    update_values(password, show_bill, waste_strategy=waste_strategy)
    if trigger == "confirm_new_password":
        return None, no_update, no_update, [no_update] * 3, True

    bad_rows_list = [[], [], []]
    open_warning_data = False          
    db = Container.get(Database)
    for i, table in enumerate(db_tables):
        if table is None:
            continue
        _, content_string = table.split(",")
        content = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        if len(df) > 0:
            open_warning_data, bad_rows = db.try_upload_values(df, table_ids[i]["index"])
            bad_rows_list[i] = bad_rows
    return TransactionResult((True, open_warning_password, open_warning_data, bad_rows_list, False), commit=not open_warning_data)


@callback(
    Output({"index": MATCH, "type": "show_upload_file"}, "children"),
    Input({"index": MATCH, "type": "database_upload"}, "filename"),
)
def show_new_upload(file):
    if file is not None and len(file) > 0:
        return str(file)
    else:
        return no_update


@callback(
    Output({"index": MATCH, "type": "download_trigger"}, "data"),
    Input({"index": MATCH, "type": "download_trigger_btn"}, "n_clicks"),
)
def download_tables(trigger):
    trigger = ctx.triggered_id
    if trigger is None:
        return no_update
    data_translation = {
        "users": get_users,
        "prods": get_prods,
        "transactions": get_trans,
    }
    trigger = trigger["index"]
    data = data_translation[trigger]().to_csv
    return dcc.send_data_frame(data, filename=f"{trigger}_data.csv", index=False)


@callback_with_error_queue(2,
    Output("payments_modal", "is_open"),
    Output("payments_download", "data"),
    Input("export_payments_btn", "n_clicks"),
    Input("confirm_payments", "n_clicks"),
    State("added_amount_inp", "value"),
    State("up_down_dd", "value"),
    State("round_dd", "value"),
)
@db_transaction_raises
def control_payments_modal(open_trigger, close_trigger, added_value, up_down, round):
    trigger = ctx.triggered_id
    if trigger == "export_payments_btn" and open_trigger:
        return True, no_update
    elif trigger == "confirm_payments" and close_trigger:
        db = Container.get(Database)
        allocate_waste(db)
        income = pd.DataFrame(get_income())
        active = income["#products"] > 0
        if active.any():
            income.loc[active, "price"] += float(added_value) / int(active.sum())
        if int(round) != 0:
            if up_down == "Nearest":
                rounding = lambda x: int(round * builtins.round(float(x) / round))
            elif up_down == "Up":
                rounding = lambda x: float(x) + round - (float(x) % round)
            else:
                rounding = lambda x: float(x) - (float(x) % round)
            positive = income["price"] > 0
            income.loc[positive, "price"] = income.loc[positive, "price"].apply(rounding)
        return False, dcc.send_data_frame(
            income.to_csv, filename="swamp_machine_payments.csv", index=False
        )
    else:
        return no_update, no_update

@callback_with_error_queue(1,
    Output("pdf_download", "data"),
    Input("export_barcodes_btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_barcodes(trigger):
    if trigger is None:
        return no_update

    types = ["users", "prods", "multipliers"]
    temp_files = []
    
    for type in types:
        pdf_filename = f"{type[:-1]}_barcodes.pdf"
        generate_pdf(
            type=type,
            pdf_filename=pdf_filename,
        )
        temp_files.append(pdf_filename)
    
    zip_buffer = io.BytesIO()
    zip_filename = f"barcodes_{datetime.now().strftime('%d_%m_%Y_%H_%M_%S')}.zip"

    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        for pdf in temp_files:
            with open(pdf, 'rb') as f:
                zipf.writestr(pdf, f.read())
    
    for pdf in temp_files:
        if os.path.exists(pdf):
            os.remove(pdf)

    zip_buffer.seek(0)
    return dcc.send_bytes(zip_buffer.getvalue(), filename=zip_filename)


@callback(
    Output("bad_rows_modal", "is_open"),
    Output({"index": ALL, "type": "bad_rows_table"}, "data"),
    Input("update_settings", "data"),
    State({"index": ALL, "type": "bad_rows"}, "data"),
)
def open_bad_rows(trigger, data):
    if (
        trigger is None
        or max([0 if table is None else len(table) for table in data]) == 0
    ):
        return no_update, [no_update, no_update, no_update]
    else:
        print(data)
        return True, data


@callback(
    Output("edit_data_modal", "is_open"),
    Output("edit_modal_row", "data"),
    Output("edit_text", "children"),
    Input("edit_users", "n_clicks"),
    Input("edit_prods", "n_clicks"),
    Input("edit_modal_delete", "n_clicks"),
    Input("edit_modal_edit", "n_clicks"),
    prevent_initial_call=True,
)
def open_edit_modal(open_user, open_prod, close_delete, close_edit):
    trigger = ctx.triggered_id
    if trigger in ["edit_users", "edit_prods"] and any(
        [trig is not None for trig in [open_user, open_prod]]
    ):
        text = "user" if "user" in trigger else "product"
        return True, trigger.split("_")[1], f"Input barcode for {text}"
    if trigger in ["edit_modal_delete", "edit_modal_edit"] and any(
        [trig is not None for trig in [close_delete, close_edit]]
    ):
        return False, None, no_update
    return no_update, no_update, no_update


@callback_with_error_queue(6,
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"index": ALL, "type": "user_input"}, "value", allow_duplicate=True),
    Output({"index": ALL, "type": "prod_input"}, "value", allow_duplicate=True),
    Output("user_table", "data", allow_duplicate=True),
    Output("prod_table", "data", allow_duplicate=True),
    Input("edit_modal_delete", "n_clicks"),
    Input("edit_modal_edit", "n_clicks"),
    State("edit_modal_row", "data"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
@db_transaction_raises
def edit_new_data_modals(delete, edit, table, barcode):
    db = Container.get(Database)
    user_table = db._user_table
    prod_table = db._product_table
    user_col_count = 5
    prod_col_count = len(prod_table.columns)

    trigger = ctx.triggered_id
    if trigger == "edit_modal_delete" and barcode is not None:
        if table == "users":
            data = user_table.get()
            other_table_data = no_update
        elif table == "prods":
            data = prod_table.get()
            other_table_data = no_update
        barcode_mask = data["barcode"] == int(barcode)
        data = data[~barcode_mask].copy()
        db.upload_values_raises(data, table)
        if table == "users":
            return (
                no_update,
                no_update,
                [no_update] * user_col_count,
                [no_update] * prod_col_count,
                data.to_dict(orient="records"),
                other_table_data,
            )
        return (
            no_update,
            no_update,
            [no_update] * user_col_count,
            [no_update] * prod_col_count,
            other_table_data,
            data.to_dict(orient="records"),
        )
    elif trigger == "edit_modal_edit" and barcode is not None:
        if table == "users":
            data = user_table.get()
            row = data[data["barcode"] == int(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update
            row_dict = row.iloc[0].to_dict()
            is_guest = int(str(row_dict.get("is_guest", 0))) == 1
            row_list = [
                row_dict["barcode"],
                row_dict["name"],
                row_dict["rank"],
                row_dict["team"],
                [1] if is_guest else [],
            ]
            return True, False, row_list, [no_update] * prod_col_count, no_update, no_update
        if table == "prods":
            data = prod_table.get()
            row = data[data["barcode"] == int(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update
            row = list(row.values[0])
            return False, True, [no_update] * user_col_count, row, no_update, no_update
    else:
        return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update


@callback_with_error_queue(1,
    Output("reset_data_modal", "is_open"),
    Input("reset_app", "n_clicks"),
    Input("delete_data_btn", "n_clicks"),
    Input("cancel_delete_data_btn", "n_clicks"),
)
def reset_database(trigger, delete, cancel):
    trigger = ctx.triggered_id
    if trigger == "reset_app":
        return True
    elif trigger == "delete_data_btn":
        reset_all_tables()
        return False
    elif trigger == "cancel_delete_data_btn":
        return False
    else:
        return no_update


@callback_with_error_queue(1,
    Output("backup_filename", "data"),
    Input("backup_interval", "n_intervals"),
    State("backup_interval", "interval"),
)
def backup_database(trigger, interval):
    if trigger is not None and interval != 0:
        if not os.path.isdir("swamp_backups"):
            os.mkdir("swamp_backups")
        filename = f"swamp_backups/beerbase_backup_{str(datetime.now().strftime('%d_%m_%Y_%H_%M_%S'))}.db"
        shutil.copy("beerbase.db", filename)
        return filename
    return no_update


@callback(Output("backup_interval", "interval"), Input("settings_backup_time", "value"))
def set_backup_timer(interval):
    if interval is not None:
        update_values(backup_time=interval)
        return interval * 60000  # Convert to minutes
    return no_update


@callback(
    Output("cache_validation_interval", "interval"),
    Input("settings_cache_validation_time", "value"),
)
def set_cache_validation_timer(interval):
    if interval is not None:
        update_values(cache_validation_time=interval)
        return interval * 60000
    return no_update


@callback(Output("study_users_modal", "is_open"), Input("study_users_btn", "n_clicks"))
def open_study_users(trigger):
    if trigger is not None:
        return True
    return no_update


@callback(Output("study_user_table", "figure"), Input("study_users_dd", "value"))
def study_users(users):
    if users is None or len(users) < 1:
        return no_update

    prods = get_prods()
    trans = get_trans().merge(
        prods, "right", left_on="barcode_prod", right_on="barcode"
    )

    if not isinstance(users, list):
        users = [users]

    study_table = list()
    for user in users:
        prod_dict = {prod: 0 for prod in list(prods["name"])}
        prod_dict["user"] = user
        user_trans = trans[trans["barcode_user"] == str(user)]
        counts = user_trans["name"].value_counts().to_dict()
        prod_dict.update(counts)
        study_table.append(prod_dict)

    return px.bar(study_table, text="user")
