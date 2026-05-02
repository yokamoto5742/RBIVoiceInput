import queue
from unittest.mock import Mock, patch
import tkinter as tk

from app.ui_queue_processor import UIQueueProcessor


class TestUIQueueProcessorInit:
    """UIQueueProcessor初期化のテストクラス"""

    def test_init_success(self):
        """正常系: UIQueueProcessorの正常初期化"""
        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.return_value = True

        processor = UIQueueProcessor(mock_master)

        assert processor.master == mock_master
        assert isinstance(processor._ui_queue, queue.Queue)
        assert processor._is_shutting_down is False


class TestUIQueueProcessorStart:
    """UIQueueProcessorのstart()メソッドのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.processor = UIQueueProcessor(self.mock_master)

    def test_start_success(self):
        """正常系: キュー処理を開始"""
        self.processor.start()

        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)

    def test_start_when_ui_invalid(self):
        """異常系: UI無効時の開始"""
        self.mock_master.winfo_exists.return_value = False

        self.processor.start()

        self.mock_master.after.assert_not_called()

    def test_start_with_tcl_error(self):
        """異常系: TclErrorが発生"""
        self.mock_master.after.side_effect = tk.TclError("invalid command")

        self.processor.start()

        # エラーをログに記録するが例外は発生しない


class TestUIQueueProcessorScheduleCallback:
    """UIQueueProcessorのschedule_callback()メソッドのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.processor = UIQueueProcessor(self.mock_master)

    def test_schedule_callback_success(self):
        """正常系: コールバックをスケジュール"""
        mock_callback = Mock()

        self.processor.schedule_callback(mock_callback, "arg1", "arg2")

        callback, args = self.processor._ui_queue.get_nowait()
        assert callback == mock_callback
        assert args == ("arg1", "arg2")

    def test_schedule_callback_no_args(self):
        """正常系: 引数なしのコールバックをスケジュール"""
        mock_callback = Mock()

        self.processor.schedule_callback(mock_callback)

        callback, args = self.processor._ui_queue.get_nowait()
        assert callback == mock_callback
        assert args == ()

    def test_schedule_callback_when_shutting_down(self):
        """異常系: シャットダウン中はスケジュールしない"""
        self.processor._is_shutting_down = True
        mock_callback = Mock()

        self.processor.schedule_callback(mock_callback)

        assert self.processor._ui_queue.empty()

    def test_schedule_callback_with_exception(self):
        """異常系: キューイング中に例外発生"""
        mock_callback = Mock()
        with patch.object(self.processor._ui_queue, 'put_nowait', side_effect=Exception("queue error")):
            self.processor.schedule_callback(mock_callback)

        # エラーをログに記録するが例外は発生しない


class TestUIQueueProcessorProcessQueue:
    """UIQueueProcessorの_process_queue()メソッドのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_master.winfo_exists.return_value = True
        self.processor = UIQueueProcessor(self.mock_master)

    def test_process_queue_executes_callbacks(self):
        """正常系: キュー内のコールバックを実行"""
        mock_callback1 = Mock()
        mock_callback2 = Mock()

        self.processor.schedule_callback(mock_callback1, "arg1")
        self.processor.schedule_callback(mock_callback2, "arg2")

        self.processor._process_queue()

        mock_callback1.assert_called_once_with("arg1")
        mock_callback2.assert_called_once_with("arg2")
        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)

    def test_process_queue_when_shutting_down(self):
        """正常系: シャットダウン中もキュー内コールバックは実行されるが、再スケジュールはされない"""
        self.processor._is_shutting_down = True
        mock_callback = Mock()

        self.processor._ui_queue.put_nowait((mock_callback, ()))
        self.processor._process_queue()

        mock_callback.assert_called_once()
        self.mock_master.after.assert_not_called()

    def test_process_queue_with_callback_exception(self):
        """異常系: コールバック実行中に例外発生"""
        mock_callback = Mock(side_effect=Exception("callback error"))

        self.processor.schedule_callback(mock_callback)
        self.processor._process_queue()

        # エラーをログに記録するが処理は継続
        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)

    def test_process_queue_with_tcl_error(self):
        """異常系: コールバック実行中にTclError発生"""
        mock_callback = Mock(side_effect=tk.TclError("invalid command"))

        self.processor.schedule_callback(mock_callback)
        self.processor._process_queue()

        # TclErrorを警告としてログに記録
        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)

    def test_process_queue_reschedules_itself(self):
        """正常系: 処理後に自分自身を再スケジュール"""
        self.processor._process_queue()

        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)

    def test_process_queue_with_after_error(self):
        """異常系: after呼び出し時にTclError発生"""
        self.mock_master.after.side_effect = [None, tk.TclError("invalid command")]

        self.processor._process_queue()

        # エラーを無視して処理を終了

    def test_process_queue_processes_up_to_10_items(self):
        """正常系: 最大10個のアイテムを処理"""
        callbacks = [Mock() for _ in range(15)]

        for cb in callbacks:
            self.processor.schedule_callback(cb)

        self.processor._process_queue()

        # 最初の10個だけ実行される
        for i in range(10):
            callbacks[i].assert_called_once()

        # 残りの5個は実行されない
        for i in range(10, 15):
            callbacks[i].assert_not_called()

    def test_process_queue_empty_queue(self):
        """正常系: 空のキューを処理"""
        self.processor._process_queue()

        self.mock_master.after.assert_called_once_with(50, self.processor._process_queue)


class TestUIQueueProcessorIsUIValid:
    """UIQueueProcessorのis_ui_valid()メソッドのテストクラス"""

    def test_is_ui_valid_true(self):
        """正常系: UIが有効"""
        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.return_value = True
        processor = UIQueueProcessor(mock_master)

        assert processor.is_ui_valid() is True

    def test_is_ui_valid_when_shutting_down(self):
        """異常系: シャットダウン中"""
        mock_master = Mock(spec=tk.Tk)
        processor = UIQueueProcessor(mock_master)
        processor._is_shutting_down = True

        assert processor.is_ui_valid() is False

    def test_is_ui_valid_master_none(self):
        """異常系: masterがNone"""
        mock_master = Mock(spec=tk.Tk)
        processor = UIQueueProcessor(mock_master)
        processor.master = None  # type: ignore

        assert processor.is_ui_valid() is False

    def test_is_ui_valid_no_winfo_exists(self):
        """異常系: winfo_existsが存在しない"""
        mock_master = Mock(spec=[])
        processor = UIQueueProcessor(mock_master)

        assert processor.is_ui_valid() is False

    def test_is_ui_valid_winfo_exists_false(self):
        """異常系: winfo_existsがFalseを返す"""
        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.return_value = False
        processor = UIQueueProcessor(mock_master)

        assert processor.is_ui_valid() is False

    def test_is_ui_valid_tcl_error(self):
        """異常系: winfo_existsでTclError発生"""
        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.side_effect = tk.TclError("invalid command")
        processor = UIQueueProcessor(mock_master)

        assert processor.is_ui_valid() is False

    def test_is_ui_valid_generic_exception(self):
        """異常系: winfo_existsで一般的な例外発生"""
        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.side_effect = Exception("unexpected error")
        processor = UIQueueProcessor(mock_master)

        assert processor.is_ui_valid() is False


class TestUIQueueProcessorShutdown:
    """UIQueueProcessorのshutdown()メソッドのテストクラス"""

    def test_shutdown_sets_flag(self):
        """正常系: シャットダウンフラグを設定"""
        mock_master = Mock(spec=tk.Tk)
        processor = UIQueueProcessor(mock_master)

        assert processor.is_shutting_down is False

        processor.shutdown()

        assert processor.is_shutting_down is True
        assert processor._is_shutting_down is True

    def test_shutdown_prevents_new_callbacks(self):
        """正常系: シャットダウン後は新しいコールバックを受け付けない"""
        mock_master = Mock(spec=tk.Tk)
        processor = UIQueueProcessor(mock_master)

        processor.shutdown()

        mock_callback = Mock()
        processor.schedule_callback(mock_callback)

        assert processor._ui_queue.empty()

    def test_is_shutting_down_property(self):
        """正常系: is_shutting_downプロパティの動作確認"""
        mock_master = Mock(spec=tk.Tk)
        processor = UIQueueProcessor(mock_master)

        assert processor.is_shutting_down is False

        processor._is_shutting_down = True

        assert processor.is_shutting_down is True


class TestUIQueueProcessorThreadSafety:
    """UIQueueProcessorのスレッドセーフ性のテストクラス"""

    def test_multiple_schedule_callbacks_thread_safe(self):
        """正常系: 複数のスレッドから安全にコールバックをスケジュール"""
        import threading

        mock_master = Mock(spec=tk.Tk)
        mock_master.winfo_exists.return_value = True
        processor = UIQueueProcessor(mock_master)

        results = []

        def add_callback(value):
            mock_callback = Mock()
            processor.schedule_callback(mock_callback, value)
            results.append(value)

        threads = [threading.Thread(target=add_callback, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 10
        assert processor._ui_queue.qsize() == 10
