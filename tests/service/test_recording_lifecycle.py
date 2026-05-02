import threading
import tkinter as tk
from unittest.mock import Mock, patch

import pytest

from service.audio_file_manager import AudioFileManager
from service.audio_recorder import AudioRecorder
from service.docs_output import DocsOutput
from service.recording_lifecycle import RecordingLifecycle
from service.transcription_handler import TranscriptionHandler
from app.ui_queue_processor import UIQueueProcessor
from tests.conftest import dict_to_app_config


def _make_lifecycle(config_dict: dict | None = None):
    if config_dict is None:
        config_dict = {
            'KEYS': {'TOGGLE_RECORDING': 'Pause'},
            'RECORDING': {'AUTO_STOP_TIMER': '60'},
            'PATHS': {'TEMP_DIR': '/test/temp'},
            'FORMATTING': {'USE_PUNCTUATION': 'True'}
        }
    config = dict_to_app_config(config_dict)
    master = Mock(spec=tk.Tk)
    master.winfo_exists.return_value = True

    recorder = Mock(spec=AudioRecorder)
    recorder.is_recording = False

    audio_file_manager = Mock(spec=AudioFileManager)
    transcription_handler = Mock(spec=TranscriptionHandler)
    transcription_handler.processing_thread = None
    transcription_handler.use_punctuation = True

    docs_output = Mock(spec=DocsOutput)
    ui_processor = Mock(spec=UIQueueProcessor)
    ui_processor.is_ui_valid.return_value = True
    ui_processor.is_shutting_down = False

    notification_callback = Mock()

    with patch('service.recording_lifecycle.RecordingTimer') as mock_timer_class:
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        lifecycle = RecordingLifecycle(
            master, config, recorder, audio_file_manager,
            transcription_handler, docs_output,
            ui_processor, notification_callback
        )
        lifecycle.recording_timer = mock_timer

    return lifecycle, master, recorder, audio_file_manager, transcription_handler, docs_output, ui_processor


def _wire_callbacks(lifecycle: RecordingLifecycle):
    update_record_button = Mock()
    update_status_label = Mock()
    lifecycle.wire_ui_callbacks(update_record_button, update_status_label)
    return update_record_button, update_status_label


class TestRecordingLifecycleInit:
    """RecordingLifecycle初期化のテストクラス"""

    def test_init_success(self):
        """正常系: 正常初期化"""
        lifecycle, master, recorder, afm, th, docs, ui = _make_lifecycle()

        assert lifecycle.master == master
        assert lifecycle.recorder == recorder
        assert lifecycle.audio_file_manager == afm
        assert lifecycle.transcription_handler == th
        assert lifecycle.docs_output == docs
        assert lifecycle.ui_processor == ui

        afm.cleanup_temp_files.assert_called_once()

    def test_wire_ui_callbacks(self):
        """正常系: UIコールバックの接続"""
        lifecycle, *_ = _make_lifecycle()
        update_btn, update_label = _wire_callbacks(lifecycle)

        assert lifecycle._ui_callbacks['update_record_button'] == update_btn
        assert lifecycle._ui_callbacks['update_status_label'] == update_label


class TestRecordingLifecycleToggleRecording:
    """toggle_recording()のテストクラス"""

    def setup_method(self):
        self.lifecycle, self.master, self.recorder, *_ = _make_lifecycle()
        _wire_callbacks(self.lifecycle)

    def test_toggle_when_not_recording_starts(self):
        """正常系: 録音中でない場合は開始"""
        self.recorder.is_recording = False

        with patch.object(self.lifecycle, 'start_recording') as mock_start:
            self.lifecycle.toggle_recording()
            mock_start.assert_called_once()

    def test_toggle_when_recording_stops(self):
        """正常系: 録音中の場合は停止"""
        self.recorder.is_recording = True

        with patch.object(self.lifecycle, 'stop_recording') as mock_stop:
            self.lifecycle.toggle_recording()
            mock_stop.assert_called_once()

    def test_toggle_runtime_error_is_swallowed(self):
        """異常系: start_recordingでRuntimeErrorが発生しても例外は上がらない"""
        self.recorder.is_recording = False

        with patch.object(self.lifecycle, 'start_recording', side_effect=RuntimeError("already running")):
            self.lifecycle.toggle_recording()  # 例外なし


class TestRecordingLifecycleStartRecording:
    """start_recording()のテストクラス"""

    def setup_method(self):
        self.lifecycle, self.master, self.recorder, _, self.th, *_ = _make_lifecycle()
        self.update_btn, self.update_label = _wire_callbacks(self.lifecycle)

    @patch('service.recording_lifecycle.threading.Thread')
    def test_start_recording_success(self, mock_thread_class):
        """正常系: 録音開始成功"""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        self.lifecycle.start_recording()

        self.th.reset_cancel.assert_called_once()
        self.recorder.start_recording.assert_called_once()
        self.update_btn.assert_called_once_with(True)
        self.update_label.assert_called_once()
        mock_thread.start.assert_called_once()
        self.lifecycle.recording_timer.start.assert_called()  # type: ignore[attr-defined]

    def test_start_recording_raises_if_thread_alive(self):
        """異常系: 処理スレッドが実行中の場合はRuntimeError"""
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.th.processing_thread = mock_thread

        with pytest.raises(RuntimeError, match="前回の処理が完了していません"):
            self.lifecycle.start_recording()


class TestRecordingLifecycleStopRecording:
    """stop_recording()のテストクラス"""

    def setup_method(self):
        self.lifecycle, self.master, self.recorder, _, self.th, *_ = _make_lifecycle()
        self.update_btn, self.update_label = _wire_callbacks(self.lifecycle)

    def test_stop_recording_success(self):
        """正常系: 録音停止成功"""
        with patch.object(self.lifecycle, '_stop_recording_process') as mock_process:
            self.lifecycle.stop_recording()
            self.lifecycle.recording_timer.cancel.assert_called()  # type: ignore[attr-defined]
            mock_process.assert_called_once()

    @patch('service.recording_lifecycle.threading.Thread')
    def test_stop_recording_process(self, mock_thread_class):
        """正常系: 録音停止処理の詳細"""
        test_frames = [b'frame1', b'frame2']
        self.recorder.stop_recording.return_value = (test_frames, 16000)

        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        self.lifecycle._stop_recording_process()

        self.recorder.stop_recording.assert_called_once()
        self.update_btn.assert_called_once_with(False)
        self.update_label.assert_called_once_with("テキスト出力中...")
        mock_thread.start.assert_called_once()

    def test_stop_recording_recorder_error(self):
        """異常系: 録音停止時のエラー"""
        self.recorder.stop_recording.side_effect = Exception("recorder error")

        with patch.object(self.lifecycle, '_safe_error_handler') as mock_handler:
            self.lifecycle._stop_recording_process()
            mock_handler.assert_called_once()


class TestRecordingLifecycleUsePunctuation:
    """use_punctuationプロパティのテストクラス"""

    def test_use_punctuation_getter(self):
        """正常系: getterが正常に動作"""
        lifecycle, *_ = _make_lifecycle()
        assert lifecycle.use_punctuation is True

    def test_use_punctuation_setter(self):
        """正常系: setterがTranscriptionHandlerも更新"""
        lifecycle, _, _, _, th, *_ = _make_lifecycle()

        lifecycle.use_punctuation = False

        assert lifecycle.use_punctuation is False
        assert th.use_punctuation is False


class TestRecordingLifecycleSafeUiUpdate:
    """_safe_ui_update()のテストクラス"""

    def test_safe_ui_update_calls_docs_append(self):
        """正常系: DocsOutput.appendを呼ぶ"""
        lifecycle, _, _, _, _, docs, ui = _make_lifecycle()
        ui.is_ui_valid.return_value = True

        lifecycle._safe_ui_update("テキスト")

        docs.append.assert_called_once_with("テキスト")

    def test_safe_ui_update_skips_when_ui_invalid(self):
        """異常系: UI無効時はスキップ"""
        lifecycle, _, _, _, _, docs, ui = _make_lifecycle()
        ui.is_ui_valid.return_value = False

        lifecycle._safe_ui_update("テキスト")

        docs.append.assert_not_called()


class TestRecordingLifecycleCleanup:
    """cleanup()のテストクラス"""

    def test_cleanup_success(self):
        """正常系: クリーンアップ成功"""
        lifecycle, _, recorder, _afm, th, _, ui = _make_lifecycle()
        _wire_callbacks(lifecycle)
        recorder.is_recording = False
        th.processing_thread = None

        lifecycle.cleanup()

        ui.shutdown.assert_called_once()
        th.cancel.assert_called_once()
        lifecycle.recording_timer.cleanup.assert_called()  # type: ignore[attr-defined]
        _afm.cleanup_temp_files.assert_called()

    def test_cleanup_stops_active_recording(self):
        """正常系: 録音中の場合は停止する"""
        lifecycle, _, recorder, _, th, _, _ = _make_lifecycle()
        _wire_callbacks(lifecycle)
        recorder.is_recording = True
        th.processing_thread = None

        with patch.object(lifecycle, 'stop_recording') as mock_stop:
            lifecycle.cleanup()
            mock_stop.assert_called_once()

    def test_cleanup_waits_for_processing_thread(self):
        """正常系: 処理スレッドの完了を待機する"""
        lifecycle, _, recorder, _, th, _, _ = _make_lifecycle()
        _wire_callbacks(lifecycle)
        recorder.is_recording = False

        mock_thread = Mock(spec=threading.Thread)
        mock_thread.is_alive.side_effect = [True] + [False] * 49
        th.processing_thread = mock_thread

        lifecycle.cleanup()

        mock_thread.is_alive.assert_called()
