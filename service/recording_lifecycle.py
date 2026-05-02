import logging
import os
import threading
import time
import tkinter as tk
from typing import Any, Callable, Dict

from app.ui_queue_processor import UIQueueProcessor
from service.audio_file_manager import AudioFileManager
from service.audio_recorder import AudioRecorder
from service.docs_output import DocsOutput
from service.recording_timer import RecordingTimer
from service.transcription_handler import TranscriptionHandler
from utils.app_config import AppConfig


class RecordingLifecycle:
    """録音開始、文字起こし、Docs出力までのライフサイクルを管理"""

    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            recorder: AudioRecorder,
            audio_file_manager: AudioFileManager,
            transcription_handler: TranscriptionHandler,
            docs_output: DocsOutput,
            ui_processor: UIQueueProcessor,
            notification_callback: Callable
    ):
        self.master = master
        self.config = config
        self.recorder = recorder
        self.audio_file_manager = audio_file_manager
        self.transcription_handler = transcription_handler
        self.docs_output = docs_output
        self.ui_processor = ui_processor
        self.show_notification = notification_callback

        self._ui_callbacks: Dict[str, Callable] = {}

        self._use_punctuation = config.use_punctuation

        self.recording_timer = RecordingTimer(
            master, config, ui_processor,
            notification_callback,
            lambda: self.recorder.is_recording,
            self._stop_recording_process
        )

        self.audio_file_manager.cleanup_temp_files()

    def wire_ui_callbacks(
            self,
            update_record_button: Callable[[bool], Any],
            update_status_label: Callable[[str], Any]
    ) -> None:
        """UIコンポーネント生成後にコールバックを接続する"""
        self._ui_callbacks = {
            'update_record_button': update_record_button,
            'update_status_label': update_status_label,
        }

    def _handle_error(self, error_msg: str) -> None:
        """エラーを処理してUIに反映する"""
        try:
            if self.ui_processor.is_ui_valid():
                self.show_notification('エラー', error_msg)
                self._ui_callbacks['update_status_label'](
                    f'{self.config.toggle_recording_key}キーで音声入力開始/停止'
                )
                self._ui_callbacks['update_record_button'](False)
                if self.recorder.is_recording:
                    self.recorder.stop_recording()
                if self.docs_output.is_available():
                    self.docs_output.clear_placeholder()
        except Exception as e:
            logging.error(f'エラーハンドリング中にエラー: {str(e)}')

    def _safe_error_handler(self, error_msg: str) -> None:
        """スレッドセーフなエラーハンドラ"""
        try:
            if self.ui_processor.is_ui_valid():
                self._handle_error(error_msg)
            else:
                logging.error(f'UI無効時のエラー: {error_msg}')
        except Exception as e:
            logging.error(f'エラーハンドリング中にエラー: {str(e)}')

    def toggle_recording(self) -> None:
        """録音の開始と停止を切り替える"""
        if not self.recorder.is_recording:
            try:
                self.start_recording()
            except RuntimeError as e:
                logging.warning(f'録音開始をスキップ: {e}')
        else:
            self.stop_recording()

    def start_recording(self) -> None:
        if (self.transcription_handler.processing_thread and
                self.transcription_handler.processing_thread.is_alive()):
            raise RuntimeError('前回の処理が完了していません')

        self.transcription_handler.reset_cancel()
        self.recorder.start_recording()
        if self.docs_output.is_available():
            self.docs_output.show_placeholder()
        self._ui_callbacks['update_record_button'](True)
        self._ui_callbacks['update_status_label'](
            f'音声入力中... ({self.config.toggle_recording_key}キーで停止)'
        )

        recording_thread = threading.Thread(target=self._safe_record, daemon=True)
        recording_thread.start()

        self.recording_timer.start()

    def _safe_record(self) -> None:
        try:
            self.recorder.record()
        except Exception as e:
            logging.error(f'録音中にエラーが発生しました: {str(e)}')
            try:
                self.master.after(0, self._safe_error_handler,
                                  f'録音中にエラーが発生しました: {str(e)}')
            except Exception:
                pass

    def stop_recording(self) -> None:
        try:
            self.recording_timer.cancel()
            self._stop_recording_process()
        except Exception as e:
            self._safe_error_handler(f'録音の停止中にエラーが発生しました: {str(e)}')

    def _stop_recording_process(self) -> None:
        """録音停止後の文字起こし処理を開始する"""
        try:
            frames, sample_rate = self.recorder.stop_recording()
            logging.info('音声データを取得しました')

            self._ui_callbacks['update_record_button'](False)
            self._ui_callbacks['update_status_label']('テキスト出力中...')

            self.transcription_handler.processing_thread = threading.Thread(
                target=self.transcription_handler.transcribe_frames,
                args=(frames, sample_rate, self._safe_ui_update, self._safe_error_handler),
                daemon=True
            )
            self.transcription_handler.processing_thread.start()

            if self.ui_processor.is_ui_valid():
                self.master.after(
                    100,
                    self._check_process_thread,
                    self.transcription_handler.processing_thread
                )
        except Exception as e:
            logging.error(f'録音停止処理中にエラー: {str(e)}')
            self._safe_error_handler(f'録音停止処理中にエラー: {str(e)}')

    def _check_process_thread(self, thread: threading.Thread) -> None:
        """処理スレッドの完了を監視し完了後にステータスを更新する"""
        try:
            if not thread.is_alive():
                self._ui_callbacks['update_status_label'](
                    f'{self.config.toggle_recording_key}キーで音声入力開始/停止'
                )
                self.transcription_handler.processing_thread = None
                return

            self._ui_callbacks['update_status_label']('テキスト出力中...')
            if self.ui_processor.is_ui_valid():
                self.master.after(100, self._check_process_thread, thread)
        except Exception as e:
            logging.error(f'処理スレッドチェック中にエラー: {str(e)}')

    def handle_audio_file(self, event: Any) -> None:
        """クリップボードから音声ファイルパスを取得して文字起こしする"""
        try:
            file_path = self.master.clipboard_get()
            if not os.path.exists(file_path):
                self.show_notification('エラー', '音声ファイルが見つかりません')
                return

            self._ui_callbacks['update_status_label']('音声ファイル処理中...')

            self.transcription_handler.handle_audio_file(
                file_path,
                self._safe_ui_update,
                lambda e: self.show_notification('エラー', e)
            )
        except Exception as e:
            self.show_notification('エラー', str(e))
        finally:
            self._ui_callbacks['update_status_label'](
                f'{self.config.toggle_recording_key}キーで音声入力開始/停止'
            )

    def _safe_ui_update(self, text: str) -> None:
        """文字起こし完了後にDocsへ追記する"""
        try:
            logging.debug(f'_safe_ui_update開始: text長={len(text)}')
            if not self.ui_processor.is_ui_valid():
                logging.warning('UIが無効なため、UI更新をスキップします')
                return
            self.docs_output.append(text)
        except Exception as e:
            logging.error(f'UI更新中にエラー: {str(e)}')

    def cleanup(self) -> None:
        """リソースをクリーンアップする"""
        try:
            logging.info('RecordingLifecycle クリーンアップ開始')
            self.ui_processor.shutdown()
            self.transcription_handler.cancel()

            if self.recorder.is_recording:
                self.stop_recording()

            if (self.transcription_handler.processing_thread and
                    self.transcription_handler.processing_thread.is_alive()):
                logging.info('処理スレッドの完了を待機中...')
                for _ in range(50):
                    if not self.transcription_handler.processing_thread.is_alive():
                        break
                    time.sleep(0.1)

                if self.transcription_handler.processing_thread.is_alive():
                    logging.warning('処理スレッドが強制終了されました')
                    self.transcription_handler.processing_thread.join(1.0)

            self.recording_timer.cleanup()
            self.audio_file_manager.cleanup_temp_files()

        except Exception as e:
            logging.error(f'クリーンアップ処理中にエラーが発生しました: {str(e)}')

    @property
    def use_punctuation(self) -> bool:
        return self._use_punctuation

    @use_punctuation.setter
    def use_punctuation(self, value: bool) -> None:
        self._use_punctuation = value
        self.transcription_handler.use_punctuation = value
