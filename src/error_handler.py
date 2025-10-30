from dash import Dash, html, dcc, Input, Output, State, Patch, callback, no_update
from datetime import datetime, timedelta
import uuid


def get_view_components():
    return [
    # ONE global queue of errors
    dcc.Store(id="error-queue", data=[]),
    # overlay that should always sit on top of the app
    html.Div(id="error-overlay", style={
        "position": "fixed", "top": 0, "left": 0, "right": 0,
        "zIndex": 9999, "pointerEvents": "none",   # let clicks pass through
        "display": "flex", "justifyContent": "center",
    }),
    dcc.Interval(id="error-gc", interval=1000, n_intervals=0)
    ]


TTL_SECONDS = 6  # how long an error stays visible
def append_error(queue,new_error):
    return (queue or []) + [new_error]

def _make_error(msg, src="test"):
    return {"id": str(uuid.uuid4()), "msg": msg, "src": src, "expires": _expires_at()}

def _now():
    return datetime.utcnow()

def _expires_at(ttl=TTL_SECONDS):
    return (_now() + timedelta(seconds=ttl)).isoformat()


# --- CONSUMER: render overlay (always on top) ---

@callback(
    Output("error-overlay", "children"),
    Input("error-queue", "data"),
)
def render_overlay(queue):
    if not queue:
        return ""

    items = []
    for e in reversed(queue):
        items.append(
            html.Div(
                [
                    html.Span(f"({e.get('src')}) {e.get('msg')}"),
                ],
                style={
                    "pointerEvents": "auto",  # allow hovering/copying text
                    "background": "rgba(220, 20, 60, 0.95)",
                    "color": "white",
                    "padding": "8px 12px",
                    "margin": "8px",
                    "borderRadius": "8px",
                    "boxShadow": "0 4px 12px rgba(0,0,0,0.2)",
                    "maxWidth": "900px",
                    "fontFamily": "system-ui, sans-serif",
                }
            )
        )
    return html.Div(items, style={"display": "flex", "flexDirection": "column", "alignItems": "center"})

# --- TIMER: prune expired messages so they disappear automatically ---

@callback(
    Output("error-queue", "data", allow_duplicate=True),
    Input("error-gc", "n_intervals"),
    State("error-queue", "data"),
    prevent_initial_call=True,
)
def gc_errors(_tick, queue):
    if not queue:
        return no_update
    now_iso = _now().isoformat()
    alive = [e for e in queue if e.get("expires", now_iso) > now_iso]
    if len(alive) == len(queue):
        return no_update
    p = Patch()
    p.clear()
    p.extend(alive)
    return p
