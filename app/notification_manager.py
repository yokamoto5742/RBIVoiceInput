import logging
import tkinter as tk
from typing import Optional

from utils.app_config import AppConfig


class NotificationManager:
    def __init__(self, master: tk.Tk, config: AppConfig):
        self.master = master
        self.config = config
        self.current_popup: Optional[tk.Toplevel] = None

    def show_timed_message(self, title: str, message: str, duration: int = 2000) -> None:
        if self.current_popup:
            try:
                self.current_popup.destroy()
            except tk.TclError:
                pass

        try:
            self.current_popup = tk.Toplevel(self.master)
            self.current_popup.title(title)
            self.current_popup.attributes('-topmost', True)

            label = tk.Label(self.current_popup, text=message)
            label.pack(padx=20, pady=20)

            self.current_popup.after(duration, self._destroy_popup)

        except Exception as e:
            logging.error(f'通知中にエラーが発生しました: {str(e)}')

    def _destroy_popup(self) -> None:
        try:
            if self.current_popup:
                self.current_popup.destroy()
        except tk.TclError:
            pass
        except Exception as e:
            logging.error(f'ポップアップ終了中にエラーが発生しました: {str(e)}')
        finally:
            self.current_popup = None

    def cleanup(self) -> None:
        if self.current_popup:
            try:
                self.current_popup.destroy()
            except tk.TclError:
                pass
