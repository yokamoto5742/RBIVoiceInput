import glob
import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, Optional

from app.replacements_editor import ReplacementsEditor
from utils.app_config import AppConfig


class UIComponents:
    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            callbacks: Dict[str, Callable]
    ):
        self.master = master
        self.config = config
        self.callbacks = callbacks
        self._toggle_recording = callbacks.get('toggle_recording', lambda: None)
        self._toggle_punctuation = callbacks.get('toggle_punctuation', lambda: None)
        self.status_label: Optional[tk.Label] = None
        self.punctuation_status_label: Optional[tk.Label] = None
        self.punctuation_button: Optional[tk.Button] = None
        self.record_button: Optional[tk.Button] = None
        self.reload_audio_button: Optional[tk.Button] = None
        self.load_audio_button: Optional[tk.Button] = None
        self.technical_terms_button: Optional[tk.Button] = None
        self.replace_button: Optional[tk.Button] = None
        self.close_button: Optional[tk.Button] = None

    def setup_ui(self, version: str) -> None:
        self.master.title(f'RBIVoiceInput v{version}')
        self.master.geometry(f'{self.config.window_width}x{self.config.window_height}')

        self.record_button = tk.Button(
            self.master,
            text='音声入力開始',
            command=self._toggle_recording,
            width=15
        )
        self.record_button.pack(pady=10)

        self.punctuation_button = tk.Button(
            self.master,
            text=f'句読点切替:{self.config.toggle_punctuation_key}',
            command=self._toggle_punctuation,
            width=15
        )
        self.punctuation_button.pack(pady=5)

        use_punctuation = self.config.use_punctuation
        self.punctuation_status_label = tk.Label(
            self.master,
            text=f'【現在句読点{"あり】" if use_punctuation else "なし】"}',
        )
        self.punctuation_status_label.pack(pady=5)

        self.reload_audio_button = tk.Button(
            self.master,
            text=f'音声再読込:{self.config.reload_audio_key}',
            command=self.reload_latest_audio,
            width=15
        )
        self.reload_audio_button.pack(pady=5)

        self.load_audio_button = tk.Button(
            self.master,
            text='音声ファイル選択',
            command=self.open_audio_file,
            width=15
        )
        self.load_audio_button.pack(pady=5)

        self.technical_terms_button = tk.Button(
            self.master,
            text='専門用語登録',
            command=self.open_technical_terms_editor,
            width=15
        )
        self.technical_terms_button.pack(pady=5)

        self.replace_button = tk.Button(
            self.master,
            text='置換辞書登録',
            command=self.open_replacements_editor,
            width=15
        )
        self.replace_button.pack(pady=5)

        self.close_button = tk.Button(
            self.master,
            text=f'閉じる:{self.config.exit_app_key}',
            command=self.callbacks.get('hide_window', lambda: None),
            width=15
        )
        self.close_button.pack(pady=5)

        self.status_label = tk.Label(
            self.master,
            text=f'{self.config.toggle_recording_key}キーで音声入力開始/停止'
        )
        self.status_label.pack(pady=10)

    def update_callbacks(self, callbacks: Dict[str, Callable]) -> None:
        self.callbacks = callbacks
        self._toggle_recording = callbacks.get('toggle_recording', self._toggle_recording)
        self._toggle_punctuation = callbacks.get('toggle_punctuation', self._toggle_punctuation)

    def update_record_button(self, is_recording: bool) -> None:
        assert self.record_button is not None
        self.record_button.config(
            text=f'音声入力{"停止" if is_recording else "開始"}:{self.config.toggle_recording_key}'
        )

    def update_punctuation_button(self, use_punctuation: bool) -> None:
        assert self.punctuation_status_label is not None
        self.punctuation_status_label.config(
            text=f'【現在句読点{"あり】" if use_punctuation else "なし】"}'
        )

    def update_status_label(self, text: str) -> None:
        assert self.status_label is not None
        self.status_label.config(text=text)

    def reload_latest_audio(self) -> None:
        latest_file = self.get_latest_audio_file()
        if latest_file:
            self.master.clipboard_clear()
            self.master.clipboard_append(latest_file)
            self.master.event_generate('<<LoadAudioFile>>')
        else:
            messagebox.showwarning('警告', '音声ファイルが見つかりません')

    def get_latest_audio_file(self) -> Optional[str]:
        try:
            files = glob.glob(os.path.join(self.config.temp_dir, '*.wav'))
            if not files:
                return None
            return max(files, key=os.path.getmtime)
        except Exception as e:
            logging.error(f'直近の音声ファイル取得中にエラー: {str(e)}')
            return None

    def open_audio_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title='音声ファイルを選択',
            filetypes=[('Wave files', '*.wav')],
            initialdir=self.config.temp_dir
        )
        if file_path:
            self.master.clipboard_clear()
            self.master.clipboard_append(file_path)
            self.master.event_generate('<<LoadAudioFile>>')

    def open_replacements_editor(self) -> None:
        ReplacementsEditor(self.master, self.config)

    def open_technical_terms_editor(self) -> None:
        ReplacementsEditor(
            self.master,
            self.config,
            file_path=self.config.google_stt_phrase_set_file,
            title='専門用語登録（1行1語）',
        )

