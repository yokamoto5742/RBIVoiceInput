import logging
import queue
import threading
import tkinter as tk
from typing import Callable


class UIQueueProcessor:
    """スレッドセーフにUI更新コールバックをTkメインスレッドで実行するキュー"""

    def __init__(self, master: tk.Tk):
        self.master = master
        self._ui_queue: queue.Queue = queue.Queue()
        self._ui_lock = threading.Lock()
        self._is_shutting_down = False

    def start(self) -> None:
        try:
            if self.is_ui_valid():
                self.master.after(50, self._process_queue)
        except tk.TclError:
            pass

    def _process_queue(self) -> None:
        processed = 0
        while processed < 10:
            try:
                callback, args = self._ui_queue.get_nowait()
                try:
                    callback(*args)
                except Exception as e:
                    logging.error(f'UIコールバック実行中にエラー: {str(e)}')
                processed += 1
            except queue.Empty:
                break
            except tk.TclError as e:
                logging.error(f'キュー処理エラー (TclError): {e}')
                break

        if not self._is_shutting_down and self.is_ui_valid():
            try:
                self.master.after(50, self._process_queue)
            except tk.TclError:
                pass

    def schedule_callback(self, callback: Callable, *args) -> None:
        if self._is_shutting_down:
            return
        try:
            self._ui_queue.put_nowait((callback, args))
        except Exception as e:
            logging.error(f'コールバックのキューへの追加に失敗: {str(e)}')

    def is_ui_valid(self) -> bool:
        if self._is_shutting_down:
            return False
        try:
            with self._ui_lock:
                return bool(self.master and self.master.winfo_exists())
        except (tk.TclError, Exception):
            return False

    @property
    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

    def shutdown(self) -> None:
        self._is_shutting_down = True
