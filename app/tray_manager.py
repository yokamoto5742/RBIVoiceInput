import sys
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

import pystray
from PIL import Image


def _get_icon_path() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return base / 'assets' / 'RBIVoiceInput.ico'


class TrayManager:
    def __init__(self, root: tk.Tk, quit_callback: Callable[[], None]) -> None:
        self._root = root
        self._quit_callback = quit_callback
        self._icon: Any = None

    def start(self) -> None:
        image = Image.open(_get_icon_path())
        menu = pystray.Menu(
            pystray.MenuItem('表示', lambda: self._root.after(0, self._show_window)),
            pystray.MenuItem('終了', lambda: self._root.after(0, self._quit_callback)),
        )
        self._icon = pystray.Icon('RBIVoiceInput', image, 'RBIVoiceInput', menu)
        self._icon.run_detached()

    def hide(self) -> None:
        self._root.withdraw()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None

    def _show_window(self) -> None:
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
