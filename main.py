import webview
import threading
import logging
import keyboard as k
from ctypes import windll
import pythonnet  # <---- Hook for .NET framework

from src.main_layout import layout_func
from app import app

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app.layout = layout_func


def run_my_server():
    app.run(debug=False)


run_in_web = False

# Run the app
if __name__ == "__main__":
    h = None
    try:
        # Disable ways of closing the app
        print("Running....")
        k.block_key("alt")
        k.block_key("windows")
        h = windll.user32.FindWindowA(b"Shell_TrayWnd", None)
        windll.user32.ShowWindow(h, 0)

        if run_in_web:
            run_my_server()
        else:
            threading.Thread(target=run_my_server, daemon=True).start()
            webview.create_window(
                "Mosemaskinen",
                "http://127.0.0.1:8050",
                fullscreen=True,
                frameless=True,
                easy_drag=False,
                on_top=True,
            )
            webview.start()
    finally:
        # Re-enable all keys and taskbars even if startup or webview fails.
        k.unhook_all()
        if h is not None:
            windll.user32.ShowWindow(h, 9)
