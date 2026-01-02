from dash import Dash, html, dcc, Input, Output, State, Patch, callback, no_update, clientside_callback
from datetime import datetime, timedelta
import uuid

ERROR_QUEUE_ID = "error-queue"
ERROR_COUNT_ID = "error-count"
ERROR_BEEP_ID  = "error-beep"
ERROR_GC_ID    = "error-gc"
ERROR_OVERLAY_ID = "error-overlay"

SHOW_ERROR_SOURCE_IN_OVERLAY = False

def get_error_view_components():
    return [
        # ONE global queue of errors
        dcc.Store(id=ERROR_QUEUE_ID, data=[]),

        #Updated clientside, to trigger sound effect:
        dcc.Store(id=ERROR_COUNT_ID, data=0),

        html.Audio(
            id=ERROR_BEEP_ID,
            src="/assets/errorSound.mp3",
            style={"display": "none"}
        ),
        # overlay that should always sit on top of the app
        html.Div(id=ERROR_OVERLAY_ID, style={
            "position": "fixed", "top": 0, "left": 0, "right": 0,
            "zIndex": 9999, "pointerEvents": "none",   # let clicks pass through
            "display": "flex", "justifyContent": "center",
        }),
        dcc.Interval(id=ERROR_GC_ID, interval=500, n_intervals=0)
    ]


def append_error(queue,msg,src="test",lifespan_seconds=6):
    return (queue or []) + [_make_error(msg,src,lifespan_seconds)]

def _make_error(msg, src,lifespan_seconds):
    return {"id": str(uuid.uuid4()), "msg": msg, "src": src, "expires": _expires_at(lifespan_seconds)}

def _expires_at(lifespan_seconds):
    return (datetime.utcnow() + timedelta(seconds=lifespan_seconds)).isoformat()

# --- CONSUMER: render overlay (always on top) ---

@callback(
    Output(ERROR_OVERLAY_ID, "children"),
    Input(ERROR_QUEUE_ID, "data"),
)
def render_overlay(queue):
    if not queue:
        return ""

    items = []
    errors_source_display = lambda e : f"({e.get('src')}) " if SHOW_ERROR_SOURCE_IN_OVERLAY else ""
    for e in reversed(queue):
        items.append(
            html.Div(
                [
                    html.Span(f"{errors_source_display(e)}{e.get('msg')}"),
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
    Output(ERROR_QUEUE_ID, "data", allow_duplicate=True),
    Input(ERROR_GC_ID, "n_intervals"),
    State(ERROR_QUEUE_ID, "data"),
    prevent_initial_call=True,
)
def gc_errors(_tick, queue):
    if not queue:
        return no_update
    now_iso = datetime.utcnow().isoformat()
    alive = [e for e in queue if e.get("expires", now_iso) > now_iso]
    if len(alive) == len(queue):
        return no_update
    p = Patch()
    p.clear()
    p.extend(alive)
    return p


#Play sound when adding error
clientside_callback(
    f"""
    function(queue, prevCount) {{
        const count = (queue || []).length;
        if (prevCount == null) {{
            prevCount = 0;
        }}

        if (count > prevCount) {{
            const audio = document.getElementById('{ERROR_BEEP_ID}');
            if (audio) {{
                try {{
                    audio.currentTime = 0;
                    audio.play();
                }} catch (e) {{
                    console.warn("Could not play error sound:", e);
                }}
            }}
        }}
        return count;
    }}
    """,
    Output(ERROR_COUNT_ID, "data"),
    Input(ERROR_QUEUE_ID, "data"),
    State(ERROR_COUNT_ID, "data"),
)
