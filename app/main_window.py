import logging
import time
import tkinter as tk
from typing import Callable

from app.notification_manager import NotificationManager
from app.ui_components import UIComponents
from service.keyboard_handler import KeyboardHandler
from service.recording_lifecycle import RecordingLifecycle
from utils.app_config import AppConfig
from utils.config_manager import save_config


class VoiceInputManager:
    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            recording_lifecycle: RecordingLifecycle,
            notification_manager: NotificationManager,
            version: str,
            hide_callback: Callable[[], None],
    ):
        self.master = master
        self.config = config
        self.version = version
        self.notification_manager = notification_manager
        self.recording_lifecycle = recording_lifecycle

        self.ui_components = UIComponents(master, config, {
            'toggle_recording': self.toggle_recording,
            'toggle_punctuation': self.toggle_punctuation,
            'reload_audio': lambda: None,
            'hide_window': hide_callback,
        })
        self.ui_components.setup_ui(version)

        self.ui_components.update_callbacks({
            'toggle_recording': self.toggle_recording,
            'toggle_punctuation': self.toggle_punctuation,
            'reload_audio': self.ui_components.reload_latest_audio,
            'hide_window': hide_callback,
        })

        recording_lifecycle.wire_ui_callbacks(
            update_record_button=self.ui_components.update_record_button,
            update_status_label=self.ui_components.update_status_label,
        )

        self.keyboard_handler = KeyboardHandler(
            master,
            config,
            self.toggle_recording,
            self.toggle_punctuation,
            self.ui_components.reload_latest_audio,
            hide_callback,
        )

        self.master.bind('<<LoadAudioFile>>', recording_lifecycle.handle_audio_file)

    def toggle_recording(self) -> None:
        self.recording_lifecycle.toggle_recording()

    def toggle_punctuation(self) -> None:
        use_punctuation = not self.recording_lifecycle.use_punctuation
        self.recording_lifecycle.use_punctuation = use_punctuation
        self.ui_components.update_punctuation_button(use_punctuation)
        logging.info(f"現在句読点: {'あり' if use_punctuation else 'なし'}")
        self.config.use_punctuation = use_punctuation
        self.config.use_comma = use_punctuation
        save_config(self.config.raw_config)

    def close_application(self) -> None:
        if getattr(self, '_closed', False):
            return
        self._closed = True

        for name, component in [
            ('recording_lifecycle', self.recording_lifecycle),
            ('keyboard_handler', self.keyboard_handler),
            ('notification_manager', self.notification_manager),
        ]:
            if component and hasattr(component, 'cleanup'):
                try:
                    component.cleanup()
                except Exception as e:
                    logging.error(f'クリーンアップ失敗 ({name}): {str(e)}')

        time.sleep(0.1)
        try:
            self.master.quit()
            self.master.destroy()
        except Exception as e:
            logging.error(f'UI終了中にエラー: {str(e)}')
