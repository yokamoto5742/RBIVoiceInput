import logging
import threading
import tkinter as tk
from typing import Callable, Optional

from app.ui_queue_processor import UIQueueProcessor
from utils.app_config import AppConfig


class RecordingTimer:

    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            ui_processor: UIQueueProcessor,
            notification_callback: Callable,
            is_recording_callback: Callable[[], bool],
            on_auto_stop: Callable
    ):
        self.master = master
        self.config = config
        self.ui_processor = ui_processor
        self.show_notification = notification_callback
        self.is_recording = is_recording_callback
        self.on_auto_stop = on_auto_stop

        self._recording_timer: Optional[threading.Timer] = None
        self._five_second_timer: Optional[str] = None
        self._five_second_notification_shown: bool = False

    def start(self) -> None:
        """タイマーを開始"""
        auto_stop_timer = self.config.auto_stop_timer
        self._recording_timer = threading.Timer(auto_stop_timer, self._auto_stop_triggered)
        self._recording_timer.start()

        self._five_second_notification_shown = False
        if self.ui_processor.is_ui_valid():
            self._five_second_timer = self.master.after(
                (auto_stop_timer - 5) * 1000,
                self._show_five_second_notification
            )

    def cancel(self) -> None:
        """タイマーをキャンセル"""
        if self._recording_timer and self._recording_timer.is_alive():
            self._recording_timer.cancel()

        if self._five_second_timer:
            try:
                if self.ui_processor.is_ui_valid():
                    self.master.after_cancel(self._five_second_timer)
            except Exception:
                pass
            self._five_second_timer = None

    def _auto_stop_triggered(self) -> None:
        self.ui_processor.schedule_callback(self._auto_stop_ui)

    def _auto_stop_ui(self) -> None:
        try:
            self.show_notification('自動停止', '音声入力を自動停止しました')
            self.on_auto_stop()
        except Exception as e:
            logging.error(f'自動停止処理中にエラー: {str(e)}')

    def _show_five_second_notification(self) -> None:
        try:
            if self.is_recording() and not self._five_second_notification_shown:
                if self.ui_processor.is_ui_valid():
                    self.master.lift()
                    self.master.attributes('-topmost', True)
                    self.master.attributes('-topmost', False)
                    self.show_notification('自動停止', 'あと5秒で音声入力を停止します')
                    self._five_second_notification_shown = True
        except Exception as e:
            logging.error(f'通知表示中にエラー: {str(e)}')

    def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        self.cancel()
