import logging
import os
import threading
from typing import List, Optional, Tuple

import pyaudio

from utils.app_config import AppConfig


class AudioRecorder:
    def __init__(self, config: AppConfig):
        self.sample_rate = config.audio_sample_rate
        self.channels = config.audio_channels
        self.chunk = config.audio_chunk
        self.frames: List[bytes] = []
        self.is_recording = False
        self.p: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        self._stream_lock = threading.Lock()
        self._stop_event = threading.Event()

        os.makedirs(config.temp_dir, exist_ok=True)

        self.logger = logging.getLogger(__name__)

    def start_recording(self) -> None:
        self._stop_event.clear()
        self.is_recording = True
        self.frames = []
        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk,
            )
            self.logger.info('音声入力を開始しました。')
        except Exception as e:
            self.logger.error(f'音声入力の開始中に予期せぬエラーが発生しました: {e}')

    def stop_recording(self) -> Tuple[List[bytes], int]:
        self.is_recording = False
        self._stop_event.set()
        with self._stream_lock:
            try:
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
            except Exception as e:
                self.logger.error(f'音声入力の停止中に予期せぬエラーが発生しました: {e}')

        try:
            if self.p:
                self.p.terminate()
        except Exception as e:
            self.logger.error(f'PyAudio終了中に予期せぬエラーが発生しました: {e}')

        self.logger.info('音声入力を停止しました。')
        return self.frames, self.sample_rate

    def record(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.stream is None:
                    raise AttributeError('ストリームが初期化されていません')
                with self._stream_lock:
                    if self._stop_event.is_set():
                        break
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
            except AttributeError:
                self.logger.error('音声入力中にストリーム初期化エラーが発生しました')
                raise
            except Exception as e:
                self.logger.error(f'音声入力中に予期せぬエラーが発生しました: {e}')
                self.is_recording = False
                break
