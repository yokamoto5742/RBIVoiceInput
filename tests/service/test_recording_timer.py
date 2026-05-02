import time
from unittest.mock import Mock
import tkinter as tk

from service.recording_timer import RecordingTimer
from app.ui_queue_processor import UIQueueProcessor
from tests.conftest import dict_to_app_config


def _make_config(auto_stop_timer: str = '60'):
    return dict_to_app_config({'RECORDING': {'AUTO_STOP_TIMER': auto_stop_timer}})


class TestRecordingTimerInit:
    """RecordingTimer初期化のテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True

        self.mock_config = _make_config()

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

    def test_init_success(self):
        """正常系: RecordingTimerの正常初期化"""
        timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

        assert timer.master == self.mock_master
        assert timer.config == self.mock_config
        assert timer.ui_processor == self.mock_ui_processor
        assert timer.show_notification == self.mock_notification
        assert timer.is_recording == self.mock_is_recording
        assert timer.on_auto_stop == self.mock_on_auto_stop
        assert timer._recording_timer is None
        assert timer._five_second_timer is None
        assert timer._five_second_notification_shown is False


class TestRecordingTimerStart:
    """RecordingTimerのstart()メソッドのテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.mock_master.after.return_value = "after_id_123"

        self.mock_config = _make_config('10')

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

        self.timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

    def test_start_creates_timers(self):
        """正常系: タイマー開始時に2つのタイマーが作成される"""
        self.timer.start()

        assert self.timer._recording_timer is not None
        assert self.timer._recording_timer.is_alive()
        assert self.timer._five_second_timer == "after_id_123"
        assert self.timer._five_second_notification_shown is False

        self.mock_master.after.assert_called_once_with(
            5000,  # (10 - 5) * 1000
            self.timer._show_five_second_notification
        )

        self.timer.cancel()

    def test_start_with_60_second_timer(self):
        """正常系: 60秒タイマーの5秒前通知スケジュール"""
        # 60秒設定のタイマーを新規作成（内部構造への直接アクセスを避ける）
        config = _make_config()
        timer = RecordingTimer(
            self.mock_master, config, self.mock_ui_processor,
            self.mock_notification, self.mock_is_recording, self.mock_on_auto_stop
        )

        timer.start()

        assert timer._recording_timer is not None
        self.mock_master.after.assert_called_once_with(
            55000,  # (60 - 5) * 1000
            timer._show_five_second_notification
        )

        timer.cancel()

    def test_start_when_ui_invalid(self):
        """異常系: UIが無効な場合"""
        self.mock_ui_processor.is_ui_valid.return_value = False

        self.timer.start()

        assert self.timer._recording_timer is not None
        assert self.timer._five_second_timer is None
        self.mock_master.after.assert_not_called()

        self.timer.cancel()


class TestRecordingTimerCancel:
    """RecordingTimerのcancel()メソッドのテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.mock_master.after.return_value = "after_id_123"

        self.mock_config = _make_config('10')

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

        self.timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

    def test_cancel_active_timers(self):
        """正常系: アクティブなタイマーをキャンセル"""
        self.timer.start()
        self.timer.cancel()

        time.sleep(0.1)

        assert self.timer._recording_timer is not None
        assert not self.timer._recording_timer.is_alive()  # type: ignore
        self.mock_master.after_cancel.assert_called_once_with("after_id_123")

    def test_cancel_no_timers(self):
        """正常系: タイマーが存在しない場合のキャンセル"""
        self.timer.cancel()

        self.mock_master.after_cancel.assert_not_called()

    def test_cancel_when_ui_invalid(self):
        """異常系: UI無効時のキャンセル"""
        self.timer.start()
        self.mock_ui_processor.is_ui_valid.return_value = False

        self.timer.cancel()

        time.sleep(0.1)

        assert not self.timer._recording_timer.is_alive()  # type: ignore
        self.mock_master.after_cancel.assert_not_called()

    def test_cancel_with_exception_on_after_cancel(self):
        """異常系: after_cancelで例外が発生"""
        self.timer.start()
        self.mock_master.after_cancel.side_effect = Exception("after_cancel error")

        self.timer.cancel()

        time.sleep(0.1)

        assert not self.timer._recording_timer.is_alive()  # type: ignore
        assert self.timer._five_second_timer is None


class TestRecordingTimerAutoStop:
    """RecordingTimerの自動停止機能のテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True

        self.mock_config = _make_config('1')

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

        self.timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

    def test_auto_stop_triggered(self):
        """正常系: 自動停止トリガー時に _auto_stop_ui をUIキューに積む"""
        # スレッドを起動せず内部メソッドを直接呼ぶことでフレーキーを回避
        self.timer._auto_stop_triggered()

        self.mock_ui_processor.schedule_callback.assert_called_once_with(
            self.timer._auto_stop_ui
        )

    def test_auto_stop_ui_callback(self):
        """正常系: 自動停止のUIコールバック実行"""
        self.timer._auto_stop_ui()

        self.mock_notification.assert_called_once_with("自動停止", "音声入力を自動停止しました")
        self.mock_on_auto_stop.assert_called_once()
        self.mock_master.after.assert_not_called()

    def test_auto_stop_ui_with_exception(self):
        """異常系: 自動停止UI処理で例外発生時は通知のみ行い after は呼ばない"""
        self.mock_on_auto_stop.side_effect = Exception("auto stop error")

        self.timer._auto_stop_ui()

        self.mock_notification.assert_called_once()
        self.mock_master.after.assert_not_called()

    def test_auto_stop_ui_when_ui_invalid(self):
        """異常系: UI無効時の自動停止"""
        self.mock_ui_processor.is_ui_valid.return_value = False

        self.timer._auto_stop_ui()

        self.mock_notification.assert_called_once()
        self.mock_on_auto_stop.assert_called_once()
        self.mock_master.after.assert_not_called()


class TestRecordingTimerFiveSecondNotification:
    """RecordingTimerの5秒前通知のテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True

        self.mock_config = _make_config('10')

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

        self.timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

    def test_five_second_notification_shown(self):
        """正常系: 5秒前通知が表示される"""
        self.timer._show_five_second_notification()

        self.mock_master.lift.assert_called_once()
        assert self.mock_master.attributes.call_count == 2
        self.mock_notification.assert_called_once_with("自動停止", "あと5秒で音声入力を停止します")
        assert self.timer._five_second_notification_shown is True

    def test_five_second_notification_when_not_recording(self):
        """異常系: 録音中でない場合は通知しない"""
        self.mock_is_recording.return_value = False

        self.timer._show_five_second_notification()

        self.mock_notification.assert_not_called()
        assert self.timer._five_second_notification_shown is False

    def test_five_second_notification_already_shown(self):
        """異常系: 既に通知が表示されている場合"""
        self.timer._five_second_notification_shown = True

        self.timer._show_five_second_notification()

        self.mock_notification.assert_not_called()

    def test_five_second_notification_ui_invalid(self):
        """異常系: UI無効時の5秒前通知"""
        self.mock_ui_processor.is_ui_valid.return_value = False

        self.timer._show_five_second_notification()

        self.mock_master.lift.assert_not_called()
        self.mock_notification.assert_not_called()

    def test_five_second_notification_with_exception(self):
        """異常系: 通知表示中に例外発生"""
        self.mock_master.lift.side_effect = Exception("lift error")

        self.timer._show_five_second_notification()

        # エラーをログに記録するが例外は発生しない


class TestRecordingTimerCleanup:
    """RecordingTimerのcleanup()メソッドのテストクラス"""

    def setup_method(self):
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.mock_master.after.return_value = "after_id_123"

        self.mock_config = _make_config('10')

        self.mock_ui_processor = Mock(spec=UIQueueProcessor)
        self.mock_ui_processor.is_ui_valid.return_value = True

        self.mock_notification = Mock()
        self.mock_is_recording = Mock(return_value=True)
        self.mock_on_auto_stop = Mock()

        self.timer = RecordingTimer(
            self.mock_master,
            self.mock_config,
            self.mock_ui_processor,
            self.mock_notification,
            self.mock_is_recording,
            self.mock_on_auto_stop
        )

    def test_cleanup_cancels_timers(self):
        """正常系: クリーンアップでタイマーがキャンセルされる"""
        self.timer.start()
        self.timer.cleanup()

        time.sleep(0.1)

        assert not self.timer._recording_timer.is_alive()  # type: ignore
        self.mock_master.after_cancel.assert_called_once()

    def test_cleanup_without_timers(self):
        """正常系: タイマーなしでクリーンアップ"""
        self.timer.cleanup()

        self.mock_master.after_cancel.assert_not_called()
