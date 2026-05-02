import logging
import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

from pynput import keyboard as pynput_keyboard

from utils.app_config import AppConfig


def _to_pynput_hotkey(key_str: str) -> str:
    """設定値の表記(例: 'pause', 'ctrl+alt+v')を pynput 形式に変換する"""
    parts = [p.strip().lower() for p in key_str.split("+") if p.strip()]
    return "+".join(p if len(p) == 1 else f"<{p}>" for p in parts)


class KeyboardHandler:
    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            toggle_recording_callback: Callable,
            toggle_punctuation_callback: Callable,
            reload_audio_callback: Callable,
            exit_key_callback: Callable,
    ):
        self.master = master
        self.config = config
        self._toggle_recording = toggle_recording_callback
        self._toggle_punctuation = toggle_punctuation_callback
        self._reload_audio = reload_audio_callback
        self._exit_key = exit_key_callback
        self._listener: Optional[pynput_keyboard.GlobalHotKeys] = None
        self.setup_keyboard_listeners()

    def setup_keyboard_listeners(self) -> None:
        bindings: List[Tuple[str, Callable]] = [
            (self.config.toggle_recording_key, self._handle_toggle_recording_key),
            (self.config.exit_app_key, self._handle_exit_key),
            (self.config.toggle_punctuation_key, self._handle_toggle_punctuation_key),
            (self.config.reload_audio_key, self._handle_reload_audio_key),
        ]
        hotkeys: Dict[str, Callable] = {}
        for key, handler in bindings:
            if not key:
                continue
            try:
                hotkeys[_to_pynput_hotkey(key)] = handler
            except Exception as e:
                logging.error(f"キーバインド変換エラー ({key}): {e}")

        if not hotkeys:
            return

        try:
            self._listener = pynput_keyboard.GlobalHotKeys(hotkeys)
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            logging.error(f"キーボードリスナーの起動に失敗しました: {e}")

    def _handle_toggle_recording_key(self) -> None:
        try:
            self.master.after(0, self._toggle_recording)
        except Exception as e:
            logging.error(f"録音トグルキー処理中にエラー: {e}")

    def _handle_exit_key(self) -> None:
        try:
            self.master.after(0, self._exit_key)
        except Exception as e:
            logging.error(f"終了キー処理中にエラー: {e}")

    def _handle_toggle_punctuation_key(self) -> None:
        try:
            self.master.after(0, self._toggle_punctuation)
        except Exception as e:
            logging.error(f"句読点トグルキー処理中にエラー: {e}")

    def _handle_reload_audio_key(self) -> None:
        try:
            self.master.after(0, self._reload_audio)
        except Exception as e:
            logging.error(f"音声リロードキー処理中にエラー: {e}")

    def cleanup(self) -> None:
        try:
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
        except Exception as e:
            logging.error(f"キーボードリスナーの解放中にエラーが発生しました: {e}")
