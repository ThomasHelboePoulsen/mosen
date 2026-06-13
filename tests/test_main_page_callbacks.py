import types

from dash import no_update

from src import main_page_callbacks


def test_payment_modal_stays_closed_when_economy_tab_renders(monkeypatch, temp_db):
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="export_payments_btn"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, None, 0, "Up", 0, []
    )

    assert result == (no_update, no_update, no_update)
