from unittest.mock import Mock, patch

from service.audio_file_manager import AudioFileManager
from service.transcription_handler import TranscriptionHandler
from app.ui_queue_processor import UIQueueProcessor
from tests.conftest import dict_to_app_config


def _make_handler(use_punctuation: bool = False, config_dict: dict | None = None):
    if config_dict is None:
        config_dict = {
            'GOOGLE_STT': {'MODEL': 'chirp_3', 'LANGUAGE': 'ja-JP'},
            'PATHS': {'TEMP_DIR': '/test/temp'}
        }
    config = dict_to_app_config(config_dict)
    client = Mock()
    audio_file_manager = Mock(spec=AudioFileManager)
    ui_processor = Mock(spec=UIQueueProcessor)
    ui_processor.is_ui_valid.return_value = True
    ui_processor.is_shutting_down = False
    handler = TranscriptionHandler(config, client, audio_file_manager, ui_processor, use_punctuation)
    return handler, config, client, audio_file_manager, ui_processor


class TestTranscriptionHandlerInit:
    """TranscriptionHandler初期化のテストクラス"""

    def test_init_success(self):
        """正常系: TranscriptionHandlerの正常初期化"""
        handler, config, client, audio_file_manager, ui_processor = _make_handler(use_punctuation=True)

        assert handler.config == config
        assert handler.client == client
        assert handler.audio_file_manager == audio_file_manager
        assert handler.ui_processor == ui_processor
        assert handler.use_punctuation is True
        assert handler.cancel_processing is False
        assert handler.processing_thread is None

    def test_init_with_punctuation_false(self):
        """正常系: 句読点処理なしで初期化"""
        handler, *_ = _make_handler()

        assert handler.use_punctuation is False


class TestTranscriptionHandlerTranscribeFrames:
    """TranscriptionHandlerのtranscribe_frames()メソッドのテストクラス"""

    def setup_method(self):
        self.mock_on_complete = Mock()
        self.mock_on_error = Mock()

    @patch('service.transcription_handler.transcribe_pcm')
    @patch('service.transcription_handler.process_punctuation')
    def test_transcribe_frames_success(self, mock_process_punct, mock_transcribe_pcm):
        """正常系: 音声フレームの文字起こし成功"""
        handler, config, _, audio_file_manager, ui_processor = _make_handler()
        frames = [b'audio_data_1', b'audio_data_2']
        sample_rate = 16000
        mock_transcribe_pcm.return_value = "文字起こし結果"
        mock_process_punct.return_value = "文字起こし結果"

        handler.transcribe_frames(frames, sample_rate, self.mock_on_complete, self.mock_on_error)

        audio_file_manager.save_audio.assert_called_once_with(frames, sample_rate)
        mock_transcribe_pcm.assert_called_once_with(
            b'audio_data_1audio_data_2', sample_rate, config, handler.client, 1
        )
        mock_process_punct.assert_called_once_with("文字起こし結果", False)
        ui_processor.schedule_callback.assert_called_once_with(
            self.mock_on_complete, "文字起こし結果"
        )

    @patch('service.transcription_handler.transcribe_pcm')
    def test_transcribe_frames_save_failure_does_not_abort(self, mock_transcribe_pcm):
        """save_audioの失敗は認識処理を止めない(アーカイブ用途のため)"""
        handler, _, _, audio_file_manager, ui_processor = _make_handler()
        audio_file_manager.save_audio.return_value = None
        mock_transcribe_pcm.return_value = "結果"

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        mock_transcribe_pcm.assert_called_once()
        ui_processor.schedule_callback.assert_called_once_with(
            self.mock_on_complete, "結果"
        )

    @patch('service.transcription_handler.transcribe_pcm')
    def test_transcribe_frames_transcription_fails(self, mock_transcribe_pcm):
        """異常系: 文字起こし失敗"""
        handler, _, _, _, ui_processor = _make_handler()
        mock_transcribe_pcm.return_value = None

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        ui_processor.schedule_callback.assert_called_once()
        args = ui_processor.schedule_callback.call_args[0]
        assert args[0] == self.mock_on_error
        assert "音声ファイルの文字起こしに失敗しました" in args[1]

    def test_transcribe_frames_cancelled_before_save(self):
        """異常系: 保存前にキャンセル"""
        handler, _, _, audio_file_manager, ui_processor = _make_handler()
        handler.cancel_processing = True

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        audio_file_manager.save_audio.assert_not_called()
        ui_processor.schedule_callback.assert_not_called()

    @patch('service.transcription_handler.transcribe_pcm')
    def test_transcribe_frames_cancelled_after_save(self, mock_transcribe_pcm):
        """異常系: 保存後にキャンセル"""
        handler, _, _, audio_file_manager, ui_processor = _make_handler()

        def cancel_on_save(*_):
            handler.cancel_processing = True
            return '/test/temp/audio.wav'

        audio_file_manager.save_audio.side_effect = cancel_on_save

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        mock_transcribe_pcm.assert_not_called()
        ui_processor.schedule_callback.assert_not_called()

    @patch('service.transcription_handler.transcribe_pcm')
    @patch('service.transcription_handler.process_punctuation')
    def test_transcribe_frames_cancelled_before_ui_update(
        self, mock_process_punct, mock_transcribe_pcm
    ):
        """異常系: UI更新前にキャンセル"""
        handler, _, _, _, ui_processor = _make_handler()
        mock_process_punct.return_value = "結果"

        def cancel_after_transcribe(*_, **__):
            handler.cancel_processing = True
            return "結果"

        mock_transcribe_pcm.side_effect = cancel_after_transcribe

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        ui_processor.schedule_callback.assert_not_called()

    def test_transcribe_frames_with_exception(self):
        """異常系: 処理中に例外発生"""
        handler, _, _, audio_file_manager, ui_processor = _make_handler()
        audio_file_manager.save_audio.side_effect = Exception("保存エラー")

        handler.transcribe_frames(
            [b'audio_data'], 16000, self.mock_on_complete, self.mock_on_error
        )

        ui_processor.schedule_callback.assert_called_once()
        args = ui_processor.schedule_callback.call_args[0]
        assert args[0] == self.mock_on_error


class TestTranscriptionHandlerHandleAudioFile:
    """TranscriptionHandlerのhandle_audio_file()メソッドのテストクラス"""

    def setup_method(self):
        self.mock_on_complete = Mock()
        self.mock_on_error = Mock()

    @patch('service.transcription_handler.transcribe_audio')
    @patch('service.transcription_handler.process_punctuation')
    def test_handle_audio_file_success(self, mock_process_punct, mock_transcribe_audio):
        """正常系: 音声ファイル処理成功"""
        handler, config, _, _, _ = _make_handler()
        mock_transcribe_audio.return_value = "文字起こし結果"
        mock_process_punct.return_value = "処理済み結果"

        handler.handle_audio_file('/test/audio.wav', self.mock_on_complete, self.mock_on_error)

        mock_transcribe_audio.assert_called_once_with(
            '/test/audio.wav', config, handler.client
        )
        mock_process_punct.assert_called_once_with("文字起こし結果", False)
        self.mock_on_complete.assert_called_once_with("処理済み結果")

    @patch('service.transcription_handler.transcribe_audio')
    def test_handle_audio_file_transcription_fails(self, mock_transcribe_audio):
        """異常系: 文字起こし失敗"""
        handler, _, _, _, _ = _make_handler()
        mock_transcribe_audio.return_value = None

        handler.handle_audio_file('/test/audio.wav', self.mock_on_complete, self.mock_on_error)

        self.mock_on_error.assert_called_once_with('音声ファイルの処理に失敗しました')

    @patch('service.transcription_handler.transcribe_audio')
    def test_handle_audio_file_with_exception(self, mock_transcribe_audio):
        """異常系: 処理中に例外発生"""
        handler, _, _, _, _ = _make_handler()
        mock_transcribe_audio.side_effect = Exception("処理エラー")

        handler.handle_audio_file('/test/audio.wav', self.mock_on_complete, self.mock_on_error)

        self.mock_on_error.assert_called_once_with('処理エラー')


class TestTranscriptionHandlerWaitForProcessing:
    """TranscriptionHandlerのwait_for_processing()メソッドのテストクラス"""

    def setup_method(self):
        self.handler, *_ = _make_handler()

    def test_wait_for_processing_no_thread(self):
        """正常系: 処理スレッドなし"""
        assert self.handler.wait_for_processing() is True

    def test_wait_for_processing_thread_completes(self):
        """正常系: 処理スレッドが完了"""
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        self.handler.processing_thread = mock_thread

        assert self.handler.wait_for_processing() is True
        mock_thread.join.assert_not_called()

    def test_wait_for_processing_thread_alive(self):
        """正常系: 処理スレッドが実行中"""
        mock_thread = Mock()
        mock_thread.is_alive.side_effect = [True, False]
        self.handler.processing_thread = mock_thread

        result = self.handler.wait_for_processing(timeout=1.0)

        mock_thread.join.assert_called_once_with(timeout=1.0)
        assert result is True

    def test_wait_for_processing_timeout(self):
        """異常系: タイムアウト"""
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.handler.processing_thread = mock_thread

        result = self.handler.wait_for_processing(timeout=0.1)

        mock_thread.join.assert_called_once_with(timeout=0.1)
        assert result is False


class TestTranscriptionHandlerCancelAndReset:
    """TranscriptionHandlerのcancel()とreset_cancel()のテストクラス"""

    def test_cancel(self):
        """正常系: 処理をキャンセル"""
        handler, *_ = _make_handler()

        assert handler.cancel_processing is False
        handler.cancel()
        assert handler.cancel_processing is True

    def test_reset_cancel(self):
        """正常系: キャンセルフラグをリセット"""
        handler, *_ = _make_handler()

        handler.cancel_processing = True
        handler.reset_cancel()
        assert handler.cancel_processing is False
