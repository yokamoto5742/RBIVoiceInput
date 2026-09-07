import logging
import threading
import traceback
from typing import Any, Callable, List, Optional

from app.ui_queue_processor import UIQueueProcessor
from external_service.google_stt_api import transcribe_audio, transcribe_pcm
from service.audio_file_manager import AudioFileManager
from service.text_transformer import process_punctuation
from utils.app_config import AppConfig


class TranscriptionHandler:

    def __init__(
            self,
            config: AppConfig,
            client: Any,
            audio_file_manager: AudioFileManager,
            ui_processor: UIQueueProcessor,
    ):
        self.config = config
        self.client = client
        self.audio_file_manager = audio_file_manager
        self.ui_processor = ui_processor

        self.cancel_processing = False
        self.processing_thread: Optional[threading.Thread] = None
        self.transcribe_audio_func = transcribe_audio
        self.transcribe_pcm_func = transcribe_pcm

    def transcribe_frames(
            self,
            frames: List[bytes],
            sample_rate: int,
            on_complete: Callable[[str], None],
            on_error: Callable[[str], None]
    ) -> None:
        """音声フレームを文字起こし処理"""
        try:
            logging.info('音声フレーム処理開始')

            if self.cancel_processing:
                logging.info('処理がキャンセルされました')
                return

            pcm_bytes = b''.join(frames)

            # 保存はアーカイブ用途。失敗しても認識処理は継続
            self.audio_file_manager.save_audio(frames, sample_rate)

            if self.cancel_processing:
                logging.info('処理がキャンセルされました')
                return

            logging.info('文字起こし開始')
            transcription = self.transcribe_pcm_func(
                pcm_bytes,
                sample_rate,
                self.config,
                self.client,
                self.config.audio_channels,
            )

            if not transcription:
                raise ValueError('音声ファイルの文字起こしに失敗しました')

            use_punctuation = self.config.use_punctuation
            logging.debug(f'句読点処理開始: use_punctuation={use_punctuation}')
            transcription = process_punctuation(transcription, use_punctuation)
            logging.debug('句読点処理完了')

            if self.cancel_processing:
                logging.info('処理がキャンセルされました')
                return

            logging.debug('UI更新をスケジュール')
            self.ui_processor.schedule_callback(on_complete, transcription)
            logging.debug('UI更新スケジュール完了')

        except Exception as e:
            logging.error(f'文字起こし処理中にエラー: {str(e)}')
            logging.debug(f'詳細: {traceback.format_exc()}')
            self.ui_processor.schedule_callback(on_error, str(e))

    def handle_audio_file(
            self,
            file_path: str,
            on_complete: Callable[[str], None],
            on_error: Callable[[str], None]
    ) -> None:
        """保存した音声ファイルを文字起こしする"""
        try:
            transcription = self.transcribe_audio_func(
                file_path,
                self.config,
                self.client
            )
            if not transcription:
                raise ValueError('音声ファイルの処理に失敗しました')

            transcription = process_punctuation(transcription, self.config.use_punctuation)
            self.ui_processor.schedule_callback(on_complete, transcription)
        except Exception as e:
            logging.error(f'音声ファイル処理中にエラー: {str(e)}')
            self.ui_processor.schedule_callback(on_error, str(e))

    def cancel(self) -> None:
        """処理をキャンセルする"""
        self.cancel_processing = True

    def reset_cancel(self) -> None:
        """キャンセルフラグをリセットする"""
        self.cancel_processing = False
