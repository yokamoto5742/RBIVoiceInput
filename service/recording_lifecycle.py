import logging
import os
import threading
import time
import tkinter as tk
from typing import Any, Callable, Optional

from app.ui_queue_processor import UIQueueProcessor
from constants import (
    MSG_AUDIO_FILE_NOT_FOUND,
    MSG_AUDIO_FILE_PROCESSING,
    MSG_RECORDING,
    MSG_TRANSCRIBING,
    TITLE_ERROR,
    idle_status,
)
from service.audio_file_manager import AudioFileManager
from service.audio_recorder import AudioRecorder
from service.firestore_output import FirestoreOutput
from service.recording_timer import RecordingTimer
from service.transcription_handler import TranscriptionHandler
from utils.app_config import AppConfig

THREAD_CHECK_INTERVAL_MS = 100
SHUTDOWN_WAIT_TICKS = 50
SHUTDOWN_WAIT_TICK_SECONDS = 0.1


class RecordingLifecycle:
    """録音開始、文字起こし、Firestore出力までのライフサイクルを管理"""

    def __init__(
            self,
            master: tk.Tk,
            config: AppConfig,
            recorder: AudioRecorder,
            audio_file_manager: AudioFileManager,
            transcription_handler: TranscriptionHandler,
            firestore_output: FirestoreOutput,
            ui_processor: UIQueueProcessor,
            notification_callback: Callable
    ):
        self.master = master
        self.config = config
        self.recorder = recorder
        self.audio_file_manager = audio_file_manager
        self.transcription_handler = transcription_handler
        self.firestore_output = firestore_output
        self.ui_processor = ui_processor
        self.show_notification = notification_callback

        self._update_record_button: Callable[[bool], Any] = lambda _: None
        self._update_status_label: Callable[[str], Any] = lambda _: None

        self.recording_timer = RecordingTimer(
            master, config, ui_processor,
            notification_callback,
            lambda: self.recorder.is_recording,
            self._stop_recording_process
        )

        self._presence_ping_id: Optional[str] = None
        self._presence_ping_interval_ms = max(1, config.presence_ping_interval) * 1000

        self.audio_file_manager.cleanup_temp_files()

    def wire_ui_callbacks(
            self,
            update_record_button: Callable[[bool], Any],
            update_status_label: Callable[[str], Any]
    ) -> None:
        """UIコンポーネント生成後にコールバックを接続する"""
        self._update_record_button = update_record_button
        self._update_status_label = update_status_label

    def _handle_error(self, error_msg: str) -> None:
        """エラーを処理してUIに反映する"""
        try:
            if self.ui_processor.is_ui_valid():
                self.show_notification(TITLE_ERROR, error_msg)
                self._update_status_label(idle_status(self.config.toggle_recording_key))
                self._update_record_button(False)
                if self.recorder.is_recording:
                    self.recorder.stop_recording()
                self._stop_presence_ping()
                self.firestore_output.update_presence(False)
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
        self.firestore_output.update_presence(True)
        self._start_presence_ping()
        self._update_record_button(True)
        self._update_status_label(
            MSG_RECORDING.format(key=self.config.toggle_recording_key)
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

            self._stop_presence_ping()
            self.firestore_output.update_presence(False)

            self._update_record_button(False)
            self._update_status_label(MSG_TRANSCRIBING)

            self.transcription_handler.processing_thread = threading.Thread(
                target=self.transcription_handler.transcribe_frames,
                args=(frames, sample_rate, self._safe_ui_update, self._safe_error_handler),
                daemon=True
            )
            self.transcription_handler.processing_thread.start()

            self._watch_process_thread(MSG_TRANSCRIBING)
        except Exception as e:
            logging.error(f'録音停止処理中にエラー: {str(e)}')
            self._safe_error_handler(f'録音停止処理中にエラー: {str(e)}')

    def _watch_process_thread(self, busy_text: str) -> None:
        """処理スレッドの完了監視を開始する"""
        thread = self.transcription_handler.processing_thread
        if thread is None or not self.ui_processor.is_ui_valid():
            return
        self.master.after(
            THREAD_CHECK_INTERVAL_MS, self._check_process_thread, thread, busy_text
        )

    def _check_process_thread(self, thread: threading.Thread, busy_text: str) -> None:
        """処理スレッドの完了を監視し完了後にステータスを更新する"""
        try:
            if not thread.is_alive():
                self._update_status_label(idle_status(self.config.toggle_recording_key))
                self.transcription_handler.processing_thread = None
                return

            self._update_status_label(busy_text)
            if self.ui_processor.is_ui_valid():
                self.master.after(
                    THREAD_CHECK_INTERVAL_MS, self._check_process_thread, thread, busy_text
                )
        except Exception as e:
            logging.error(f'処理スレッドチェック中にエラー: {str(e)}')

    def handle_audio_file(self, file_path: str) -> None:
        """指定された音声ファイルをワーカースレッドで文字起こしする"""
        if not os.path.exists(file_path):
            self.show_notification(TITLE_ERROR, MSG_AUDIO_FILE_NOT_FOUND)
            return

        if (self.transcription_handler.processing_thread and
                self.transcription_handler.processing_thread.is_alive()):
            logging.warning('前回の処理が完了していないため音声ファイル処理をスキップします')
            return

        self.transcription_handler.reset_cancel()
        self._update_status_label(MSG_AUDIO_FILE_PROCESSING)

        self.transcription_handler.processing_thread = threading.Thread(
            target=self.transcription_handler.handle_audio_file,
            args=(file_path, self._safe_ui_update, self._safe_error_handler),
            daemon=True
        )
        self.transcription_handler.processing_thread.start()

        self._watch_process_thread(MSG_AUDIO_FILE_PROCESSING)

    def _safe_ui_update(self, text: str) -> None:
        """文字起こし完了後にFirestoreへ追記する"""
        try:
            logging.debug(f'_safe_ui_update開始: text長={len(text)}')
            if not self.ui_processor.is_ui_valid():
                logging.warning('UIが無効なため、UI更新をスキップします')
                return
            self.firestore_output.append(text)
        except Exception as e:
            logging.error(f'UI更新中にエラー: {str(e)}')

    def _start_presence_ping(self) -> None:
        """録音中の lastPing を定期更新する"""
        if not self.firestore_output.is_available():
            return
        if not self.ui_processor.is_ui_valid():
            return
        try:
            self._presence_ping_id = self.master.after(
                self._presence_ping_interval_ms, self._presence_ping_tick
            )
        except Exception as e:
            logging.error(f'presence ping 起動中にエラー: {str(e)}')

    def _presence_ping_tick(self) -> None:
        try:
            if not self.recorder.is_recording:
                self._presence_ping_id = None
                return
            self.firestore_output.update_presence(True)
            if self.ui_processor.is_ui_valid():
                self._presence_ping_id = self.master.after(
                    self._presence_ping_interval_ms, self._presence_ping_tick
                )
        except Exception as e:
            logging.error(f'presence ping 中にエラー: {str(e)}')

    def _stop_presence_ping(self) -> None:
        if self._presence_ping_id is None:
            return
        try:
            if self.ui_processor.is_ui_valid():
                self.master.after_cancel(self._presence_ping_id)
        except Exception:
            pass
        self._presence_ping_id = None

    def cleanup(self) -> None:
        """リソースをクリーンアップする"""
        try:
            logging.info('RecordingLifecycle クリーンアップ開始')
            self.transcription_handler.cancel()
            self._stop_presence_ping()
            self.firestore_output.update_presence(False)

            if self.recorder.is_recording:
                # 終了時は文字起こしを開始せず録音だけ止める
                self.recording_timer.cancel()
                self.recorder.stop_recording()

            self.ui_processor.shutdown()

            if (self.transcription_handler.processing_thread and
                    self.transcription_handler.processing_thread.is_alive()):
                logging.info('処理スレッドの完了を待機中...')
                for _ in range(SHUTDOWN_WAIT_TICKS):
                    if not self.transcription_handler.processing_thread.is_alive():
                        break
                    time.sleep(SHUTDOWN_WAIT_TICK_SECONDS)

                if self.transcription_handler.processing_thread.is_alive():
                    logging.warning('処理スレッドが強制終了されました')
                    self.transcription_handler.processing_thread.join(1.0)

            self.recording_timer.cancel()
            self.audio_file_manager.cleanup_temp_files()

        except Exception as e:
            logging.error(f'クリーンアップ処理中にエラーが発生しました: {str(e)}')
