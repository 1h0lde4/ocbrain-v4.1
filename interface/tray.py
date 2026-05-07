"""
interface/tray.py — System tray icon using pystray.
Works on Linux (AppIndicator), Windows, macOS.
"""
import threading
import webbrowser
from pathlib import Path
from typing import Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

from core.config import config

_icon: Optional[object] = None
PORT = 7437


def _make_icon_image() -> "Image.Image":
    """Generate a simple icon if no icon file exists."""
    icon_path = Path(__file__).parent / "web" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path)
    img  = Image.new("RGB", (64, 64), color=(30, 158, 117))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "OC", fill="white")
    return img


def _open_ui(icon, item):
    webbrowser.open(f"http://localhost:{PORT}")


def _open_settings(icon, item):
    webbrowser.open(f"http://localhost:{PORT}/static/settings.html")


def _toggle_learning(icon, item):
    current = config.get("learning.training_enabled", True)
    config.set("learning.training_enabled", not current)
    label = "Resume learning" if current else "Pause learning"
    print(f"[tray] Learning {'paused' if current else 'resumed'}")


def _check_updates(icon, item):
    from interface.updater import check
    result = check()
    if result.available:
        print(f"[tray] Update available: v{result.version}")
    else:
        print("[tray] OCBrain is up to date.")


def _quit_app(icon, item):
    icon.stop()
    import os, signal
    os.kill(os.getpid(), signal.SIGTERM)


def start(orchestrator=None):
    if not TRAY_AVAILABLE:
        print("[tray] pystray or Pillow not installed — tray icon disabled.")
        return

    def _build_menu():
        learning_on = config.get("learning.training_enabled", True)
        return pystray.Menu(
            pystray.MenuItem("Open OCBrain",    _open_ui, default=True),
            pystray.MenuItem("Settings",         _open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause learning" if learning_on else "Resume learning",
                _toggle_learning,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Check for updates", _check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",             _quit_app),
        )

    global _icon
    _icon = pystray.Icon(
        "OCBrain",
        _make_icon_image(),
        "OCBrain",
        menu=_build_menu(),
    )

    t = threading.Thread(target=_icon.run, daemon=True)
    t.start()
    print("[tray] System tray icon started.")
