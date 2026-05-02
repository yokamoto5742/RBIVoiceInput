import logging
import threading
import time
from unittest.mock import Mock, patch

import pyaudio
import pytest

from service.audio_recorder import AudioRecorder
from tests.conftest import dict_to_app_config


class TestAudioRecorderInit:
    """AudioRecorder初期化のテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'AUDIO': {
                'SAMPLE_RATE': '16000',
                'CHANNELS': '1',
                'CHUNK': '1024'
            },
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            }
        }

    @patch('service.audio_recorder.os.makedirs')
    def test_audio_recorder_init_success(self, mock_makedirs):
        """正常系: AudioRecorder正常初期化"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        assert recorder.sample_rate == 16000
        assert recorder.channels == 1
        assert recorder.chunk == 1024
        assert recorder.frames == []
        assert recorder.is_recording is False
        assert recorder.p is None
        assert recorder.stream is None
        mock_makedirs.assert_called_once_with('/test/temp', exist_ok=True)

    @patch('service.audio_recorder.os.makedirs')
    def test_audio_recorder_init_with_different_config(self, mock_makedirs):
        """正常系: 異なる設定値での初期化"""
        custom_config = {
            'AUDIO': {
                'SAMPLE_RATE': '44100',
                'CHANNELS': '2',
                'CHUNK': '2048'
            },
            'PATHS': {
                'TEMP_DIR': '/custom/temp'
            }
        }

        recorder = AudioRecorder(dict_to_app_config(custom_config))

        assert recorder.sample_rate == 44100
        assert recorder.channels == 2
        assert recorder.chunk == 2048

    @patch('service.audio_recorder.os.makedirs')
    def test_audio_recorder_init_existing_directory(self, mock_makedirs):
        """正常系: 既存ディレクトリがある場合"""
        mock_makedirs.side_effect = None

        _recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_makedirs.assert_called_once_with('/test/temp', exist_ok=True)

    @patch('service.audio_recorder.os.makedirs')
    def test_audio_recorder_init_directory_creation_error(self, mock_makedirs):
        """異常系: ディレクトリ作成エラー（権限不足等）"""
        mock_makedirs.side_effect = PermissionError("Permission denied")

        with pytest.raises(PermissionError):
            AudioRecorder(dict_to_app_config(self.mock_config))


class TestAudioRecorderStartRecording:
    """録音開始のテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'AUDIO': {
                'SAMPLE_RATE': '16000',
                'CHANNELS': '1',
                'CHUNK': '1024'
            },
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            }
        }

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_start_recording_success(self, mock_pyaudio_class, mock_makedirs):
        """正常系: 録音開始成功"""
        mock_pyaudio_instance = Mock()
        mock_stream = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.open.return_value = mock_stream

        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.start_recording()

        assert recorder.is_recording is True
        assert recorder.frames == []
        assert recorder.p == mock_pyaudio_instance
        assert recorder.stream == mock_stream
        mock_pyaudio_class.assert_called_once()
        mock_pyaudio_instance.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
        )

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_start_recording_pyaudio_initialization_error(self, mock_pyaudio_class, mock_makedirs):
        """異常系: PyAudio初期化エラー"""
        mock_pyaudio_class.side_effect = Exception("PyAudio initialization failed")
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.start_recording()

        assert recorder.is_recording is True
        assert recorder.p is None
        assert recorder.stream is None

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_start_recording_stream_open_error(self, mock_pyaudio_class, mock_makedirs):
        """異常系: ストリーム開始エラー"""
        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.open.side_effect = Exception("Stream open failed")

        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.start_recording()

        assert recorder.is_recording is True
        assert recorder.p == mock_pyaudio_instance
        assert recorder.stream is None

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_start_recording_multiple_calls(self, mock_pyaudio_class, mock_makedirs):
        """境界値: 複数回start_recordingを呼んだ場合"""
        mock_pyaudio_instance = Mock()
        mock_stream = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.open.return_value = mock_stream

        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.start_recording()
        recorder.start_recording()

        assert mock_pyaudio_class.call_count == 2
        assert mock_pyaudio_instance.open.call_count == 2


class TestAudioRecorderStopRecording:
    """録音停止のテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'AUDIO': {
                'SAMPLE_RATE': '16000',
                'CHANNELS': '1',
                'CHUNK': '1024'
            },
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            }
        }

    @patch('service.audio_recorder.os.makedirs')
    def test_stop_recording_success(self, mock_makedirs):
        """正常系: 録音停止成功"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_stream = Mock()
        mock_pyaudio = Mock()
        recorder.stream = mock_stream
        recorder.p = mock_pyaudio
        recorder.is_recording = True
        recorder.frames = [b'test_frame_1', b'test_frame_2']

        frames, sample_rate = recorder.stop_recording()

        assert recorder.is_recording is False
        assert frames == [b'test_frame_1', b'test_frame_2']
        assert sample_rate == 16000
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pyaudio.terminate.assert_called_once()

    @patch('service.audio_recorder.os.makedirs')
    def test_stop_recording_no_stream(self, mock_makedirs):
        """境界値: ストリームが存在しない場合"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.is_recording = True
        recorder.frames = [b'test_data']

        frames, sample_rate = recorder.stop_recording()

        assert recorder.is_recording is False
        assert frames == [b'test_data']
        assert sample_rate == 16000

    @patch('service.audio_recorder.os.makedirs')
    def test_stop_recording_stream_error(self, mock_makedirs):
        """異常系: ストリーム停止時のエラー"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_stream = Mock()
        mock_stream.stop_stream.side_effect = Exception("Stream stop error")
        mock_pyaudio = Mock()

        recorder.stream = mock_stream
        recorder.p = mock_pyaudio
        recorder.is_recording = True
        recorder.frames = [b'test_data']

        frames, _sample_rate = recorder.stop_recording()

        assert recorder.is_recording is False
        assert frames == [b'test_data']
        mock_pyaudio.terminate.assert_called_once()

    @patch('service.audio_recorder.os.makedirs')
    def test_stop_recording_pyaudio_terminate_error(self, mock_makedirs):
        """異常系: PyAudio終了時のエラー"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_stream = Mock()
        mock_pyaudio = Mock()
        mock_pyaudio.terminate.side_effect = Exception("PyAudio terminate error")

        recorder.stream = mock_stream
        recorder.p = mock_pyaudio
        recorder.is_recording = True
        recorder.frames = [b'audio_data']

        frames, sample_rate = recorder.stop_recording()

        assert recorder.is_recording is False
        assert frames == [b'audio_data']
        assert sample_rate == 16000

    @patch('service.audio_recorder.os.makedirs')
    def test_stop_recording_empty_frames(self, mock_makedirs):
        """境界値: 録音データが空の場合"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.is_recording = True
        recorder.frames = []

        frames, sample_rate = recorder.stop_recording()

        assert frames == []
        assert sample_rate == 16000
        assert recorder.is_recording is False


class TestAudioRecorderRecord:
    """録音処理のテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'AUDIO': {
                'SAMPLE_RATE': '16000',
                'CHANNELS': '1',
                'CHUNK': '1024'
            },
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            }
        }

    @patch('service.audio_recorder.os.makedirs')
    def test_record_success(self, mock_makedirs):
        """正常系: 録音処理成功"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_stream = Mock()
        test_data = [b'chunk1', b'chunk2', b'chunk3']
        mock_stream.read.side_effect = test_data + [Exception("Stop recording")]

        recorder.stream = mock_stream
        recorder.is_recording = True

        def stop_after_reads():
            time.sleep(0.01)
            recorder.is_recording = False

        threading.Thread(target=stop_after_reads, daemon=True).start()

        recorder.record()

        assert len(recorder.frames) >= 3
        assert recorder.frames[:3] == test_data

    @patch('service.audio_recorder.os.makedirs')
    def test_record_stream_read_error(self, mock_makedirs):
        """異常系: ストリーム読み取りエラー"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        mock_stream = Mock()
        mock_stream.read.side_effect = Exception("Stream read error")

        recorder.stream = mock_stream
        recorder.is_recording = True

        recorder.record()

        assert recorder.is_recording is False
        assert recorder.frames == []

    @patch('service.audio_recorder.os.makedirs')
    def test_record_immediate_stop(self, mock_makedirs):
        """境界値: 即座に停止される場合"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder._stop_event.set()

        recorder.record()

        assert recorder.frames == []

    @patch('service.audio_recorder.os.makedirs')
    def test_record_no_stream(self, mock_makedirs):
        """異常系: ストリームが存在しない場合"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.stream = None
        recorder.is_recording = True

        with pytest.raises(AttributeError):
            recorder.record()


class TestIntegrationScenarios:
    """統合シナリオテスト"""

    def setup_method(self):
        self.mock_config = {
            'AUDIO': {
                'SAMPLE_RATE': '16000',
                'CHANNELS': '1',
                'CHUNK': '1024'
            },
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            }
        }

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_recording_error_recovery(self, mock_pyaudio_class, mock_makedirs):
        """異常系: 録音エラーからの回復"""
        mock_pyaudio_class.side_effect = Exception("PyAudio not available")

        recorder = AudioRecorder(dict_to_app_config(self.mock_config))
        recorder.start_recording()
        frames, sample_rate = recorder.stop_recording()

        assert frames == []
        assert sample_rate == 16000
        assert recorder.is_recording is False

    @patch('service.audio_recorder.os.makedirs')
    def test_multiple_recording_sessions(self, mock_makedirs):
        """正常系: 複数回の録音セッション"""
        recorder = AudioRecorder(dict_to_app_config(self.mock_config))

        with patch('service.audio_recorder.pyaudio.PyAudio') as mock_pyaudio1:
            mock_stream1 = Mock()
            mock_pyaudio1.return_value.open.return_value = mock_stream1

            recorder.start_recording()
            recorder.frames = [b'session1_data']
            frames1, rate1 = recorder.stop_recording()

        with patch('service.audio_recorder.pyaudio.PyAudio') as mock_pyaudio2:
            mock_stream2 = Mock()
            mock_pyaudio2.return_value.open.return_value = mock_stream2

            recorder.start_recording()
            recorder.frames = [b'session2_data']
            frames2, rate2 = recorder.stop_recording()

        assert frames1 == [b'session1_data']
        assert frames2 == [b'session2_data']
        assert rate1 == rate2 == 16000


class TestErrorHandling:
    """エラーハンドリングの詳細テスト"""

    @patch('service.audio_recorder.os.makedirs')
    def test_comprehensive_error_logging(self, mock_makedirs, caplog):
        """包括的なエラーログ出力確認"""
        caplog.set_level(logging.ERROR)
        config = {
            'AUDIO': {'SAMPLE_RATE': '16000', 'CHANNELS': '1', 'CHUNK': '1024'},
            'PATHS': {'TEMP_DIR': '/test/temp'}
        }

        with patch('service.audio_recorder.pyaudio.PyAudio') as mock_pyaudio:
            mock_pyaudio.side_effect = Exception("Critical PyAudio error")

            recorder = AudioRecorder(dict_to_app_config(config))
            recorder.start_recording()

            assert "音声入力の開始中に予期せぬエラーが発生しました" in caplog.text

    @patch('service.audio_recorder.os.makedirs')
    @patch('service.audio_recorder.pyaudio.PyAudio')
    def test_stream_read_exception_handling(self, mock_pyaudio_class, mock_makedirs, caplog):
        """ストリーム読み取り例外の詳細処理"""
        caplog.set_level(logging.ERROR)
        config = {
            'AUDIO': {'SAMPLE_RATE': '16000', 'CHANNELS': '1', 'CHUNK': '1024'},
            'PATHS': {'TEMP_DIR': '/test/temp'}
        }

        mock_stream = Mock()
        mock_stream.read.side_effect = OSError("Audio device disconnected")
        mock_pyaudio_class.return_value.open.return_value = mock_stream

        recorder = AudioRecorder(dict_to_app_config(config))
        recorder.stream = mock_stream
        recorder.is_recording = True

        recorder.record()

        assert recorder.is_recording is False
        assert "音声入力中に予期せぬエラーが発生しました" in caplog.text
