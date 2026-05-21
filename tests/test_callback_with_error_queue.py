from dash import Input, Output, no_update

from src.database.data_connection import Result
from src.error_handler import callback_with_error_queue


def test_callback_with_error_queue_passes_through_single_output():
    @callback_with_error_queue(
        1,
        Output("single-output", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return "ok"

    assert handler(1, []) == ("ok", no_update)


def test_callback_with_error_queue_unwraps_result_values():
    @callback_with_error_queue(
        2,
        Output("first", "children"),
        Output("second", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return Result(values=("one", "two"))

    assert handler(1, []) == ("one", "two", no_update)


def test_callback_with_error_queue_adds_error_and_no_updates_on_exception():
    @callback_with_error_queue(
        1,
        Output("single-output", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        raise RuntimeError("boom")

    result = handler(1, [])

    assert result[0] is no_update
    assert result[1][0]["msg"] == "boom"


def test_callback_with_error_queue_preserves_result_error_when_shape_is_wrong():
    @callback_with_error_queue(
        2,
        Output("first", "children"),
        Output("second", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return Result(values=("only-one",), error=RuntimeError("inner boom"))

    result = handler(1, [])

    assert result[0] is no_update
    assert result[1] is no_update
    assert result[2][0]["msg"] == "inner boom"
    assert result[2][1]["msg"] == "Expected 2 outputs, got 1"