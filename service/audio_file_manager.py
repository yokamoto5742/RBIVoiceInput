import glob
import logging
import os
import wave
from datetime import datetime, timedelta
from typing import List, Optional

import pyaudio

from utils.app_config import AppConfig


class AudioFileManager:
    """音声ファイルの保存と一時ファイルのクリーンアップを管理する"""

    def __init__(self, config: AppConfig):
        self._config = config

    def save_audio(self, frames: List[bytes], sample_rate: int) -> Optional[str]:
        """音声フレームをWAVファイルとして保存しパスを返す"""
        try:
            temp_dir = self._config.temp_dir
            os.makedirs(temp_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_path = os.path.join(temp_dir, f'audio_{timestamp}.wav')

            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(self._config.audio_channels)
                wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(frames))

            logging.info(f'音声ファイル保存完了: {temp_path}')
            return temp_path

        except Exception as e:
            logging.error(f'音声ファイル保存エラー: {str(e)}')
            return None

    def cleanup_temp_files(self) -> None:
        """保存期間を超えた一時ファイルを削除"""
        try:
            current_time = datetime.now()
            pattern = os.path.join(self._config.temp_dir, '*.wav')

            for file_path in glob.glob(pattern):
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                if current_time - file_modified > timedelta(minutes=self._config.cleanup_minutes):
                    try:
                        os.remove(file_path)
                        logging.info(f'古い音声ファイルを削除しました: {file_path}')
                    except Exception as e:
                        logging.error(f'ファイル削除中にエラーが発生しました: {file_path}, {e}')

        except Exception as e:
            logging.error(f'クリーンアップ処理中にエラーが発生しました: {e}')
