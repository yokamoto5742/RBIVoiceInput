import logging
import os
import time
from unittest.mock import Mock, patch

from service.audio_file_manager import AudioFileManager
from tests.conftest import dict_to_app_config


class TestAudioFileManagerSaveAudio:
    """AudioFileManager.save_audioのテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'PATHS': {
                'TEMP_DIR': '/test/temp'
            },
            'AUDIO': {
                'CHANNELS': '1'
            }
        }
        self.test_frames = [b'frame1', b'frame2', b'frame3']
        self.sample_rate = 16000

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_success(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs):
        """正常系: 音声ファイル保存成功"""
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        result = manager.save_audio(self.test_frames, self.sample_rate)

        expected_path = os.path.join('/test/temp', 'audio_20240101_120000.wav')
        assert result == expected_path
        mock_wave_file.setnchannels.assert_called_once_with(1)
        mock_wave_file.setsampwidth.assert_called_once_with(2)
        mock_wave_file.setframerate.assert_called_once_with(16000)
        mock_wave_file.writeframes.assert_called_once_with(b'frame1frame2frame3')

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_empty_frames(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs):
        """境界値: 空のフレームデータ"""
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        result = manager.save_audio([], self.sample_rate)

        assert result is not None
        mock_wave_file.writeframes.assert_called_once_with(b'')

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_stereo_channels(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs):
        """正常系: ステレオ音声の保存"""
        stereo_config = {
            'PATHS': {'TEMP_DIR': '/test/temp'},
            'AUDIO': {'CHANNELS': '2'}
        }
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        manager = AudioFileManager(dict_to_app_config(stereo_config))
        result = manager.save_audio(self.test_frames, self.sample_rate)

        assert result is not None
        mock_wave_file.setnchannels.assert_called_once_with(2)

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_different_sample_rates(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs):
        """正常系: 異なるサンプルレート"""
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        result = manager.save_audio(self.test_frames, 44100)

        assert result is not None
        mock_wave_file.setframerate.assert_called_once_with(44100)

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_wave_file_error(self, mock_datetime, mock_makedirs, mock_wave_open):
        """異常系: WAVファイル作成エラー"""
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"
        mock_wave_open.side_effect = Exception("Wave file creation error")

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        result = manager.save_audio(self.test_frames, self.sample_rate)

        assert result is None

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_save_audio_logging(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs, caplog):
        """ログ出力の確認"""
        caplog.set_level(logging.INFO)
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        result = manager.save_audio(self.test_frames, self.sample_rate)

        assert result is not None
        assert "音声ファイル保存完了" in caplog.text


class TestAudioFileManagerPerformance:
    """AudioFileManagerのパフォーマンステスト"""

    @patch('service.audio_file_manager.os.makedirs')
    @patch('service.audio_file_manager.wave.open')
    @patch('service.audio_file_manager.pyaudio.PyAudio')
    @patch('service.audio_file_manager.datetime')
    def test_large_audio_data_performance(self, mock_datetime, mock_pyaudio_class, mock_wave_open, mock_makedirs):
        """大量音声データの処理性能テスト"""
        mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

        large_frames = [b'x' * 1024 for _ in range(160)]

        mock_wave_file = Mock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file

        mock_pyaudio_instance = Mock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        mock_pyaudio_instance.get_sample_size.return_value = 2

        config = {
            'PATHS': {'TEMP_DIR': '/test/temp'},
            'AUDIO': {'CHANNELS': '1'}
        }

        manager = AudioFileManager(dict_to_app_config(config))

        start_time = time.time()
        result = manager.save_audio(large_frames, 16000)
        end_time = time.time()

        assert result is not None
        assert (end_time - start_time) < 1.0


class TestAudioFileManagerCleanup:
    """AudioFileManager.cleanup_temp_filesのテストクラス"""

    def setup_method(self):
        self.mock_config = {
            'PATHS': {
                'TEMP_DIR': '/test/temp',
                'CLEANUP_MINUTES': '240'
            },
            'AUDIO': {
                'CHANNELS': '1'
            }
        }

    @patch('service.audio_file_manager.glob.glob')
    @patch('service.audio_file_manager.os.path.getmtime')
    @patch('service.audio_file_manager.os.remove')
    @patch('service.audio_file_manager.datetime')
    def test_cleanup_removes_old_files(self, mock_datetime, mock_remove, mock_getmtime, mock_glob):
        """正常系: 古いファイルが削除される"""
        from datetime import datetime as real_datetime, timedelta
        now = real_datetime(2024, 1, 1, 12)
        mock_datetime.now.return_value = now
        mock_datetime.fromtimestamp.return_value = now - timedelta(minutes=300)

        mock_glob.return_value = ['/test/temp/audio_old.wav']

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        manager.cleanup_temp_files()

        mock_remove.assert_called_once_with('/test/temp/audio_old.wav')

    @patch('service.audio_file_manager.glob.glob')
    @patch('service.audio_file_manager.os.path.getmtime')
    @patch('service.audio_file_manager.os.remove')
    @patch('service.audio_file_manager.datetime')
    def test_cleanup_keeps_recent_files(self, mock_datetime, mock_remove, mock_getmtime, mock_glob):
        """正常系: 新しいファイルは削除されない"""
        from datetime import datetime as real_datetime, timedelta
        now = real_datetime(2024, 1, 1, 12)
        mock_datetime.now.return_value = now
        mock_datetime.fromtimestamp.return_value = now - timedelta(minutes=10)

        mock_glob.return_value = ['/test/temp/audio_recent.wav']

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        manager.cleanup_temp_files()

        mock_remove.assert_not_called()

    @patch('service.audio_file_manager.glob.glob')
    def test_cleanup_no_files(self, mock_glob):
        """境界値: 対象ファイルなし"""
        mock_glob.return_value = []

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        manager.cleanup_temp_files()  # エラーなく完了

    @patch('service.audio_file_manager.glob.glob')
    @patch('service.audio_file_manager.os.path.getmtime')
    @patch('service.audio_file_manager.os.remove')
    @patch('service.audio_file_manager.datetime')
    def test_cleanup_file_remove_error_continues(
        self, mock_datetime, mock_remove, mock_getmtime, mock_glob, caplog
    ):
        """異常系: 1ファイルの削除失敗でも残りのファイルの処理を継続する"""
        from datetime import datetime as real_datetime, timedelta
        caplog.set_level(logging.ERROR)
        now = real_datetime(2024, 1, 1, 12)
        mock_datetime.now.return_value = now
        mock_datetime.fromtimestamp.return_value = now - timedelta(minutes=300)

        mock_glob.return_value = ['/test/temp/audio_1.wav', '/test/temp/audio_2.wav']
        # 1件目の削除は失敗、2件目は成功
        mock_remove.side_effect = [PermissionError("ファイルがロックされています"), None]

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        manager.cleanup_temp_files()

        # 2件ともremoveを試みる
        assert mock_remove.call_count == 2
        assert "ファイル削除中にエラーが発生しました" in caplog.text

    @patch('service.audio_file_manager.glob.glob')
    def test_cleanup_outer_error_logged(self, mock_glob, caplog):
        """異常系: glob処理自体が失敗した場合にエラーログが出力される"""
        caplog.set_level(logging.ERROR)
        mock_glob.side_effect = OSError("glob失敗")

        manager = AudioFileManager(dict_to_app_config(self.mock_config))
        manager.cleanup_temp_files()

        assert "クリーンアップ処理中にエラーが発生しました" in caplog.text
