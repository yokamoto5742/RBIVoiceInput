import logging
import tkinter as tk
from unittest.mock import Mock, patch

from app.notification_manager import NotificationManager
from tests.conftest import dict_to_app_config


class TestNotificationManagerInit:
    """NotificationManager初期化のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }

    def test_notification_manager_init_success(self):
        """正常系: NotificationManager正常初期化"""
        # Act
        manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

        # Assert
        assert manager.master == self.mock_master
        assert manager.config.toggle_recording_key == self.mock_config['KEYS']['TOGGLE_RECORDING']
        assert manager.current_popup is None

    def test_notification_manager_init_with_different_config(self):
        """正常系: 異なる設定での初期化"""
        # Arrange
        custom_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'Pause'
            }
        }

        # Act
        manager = NotificationManager(self.mock_master, dict_to_app_config(custom_config))

        # Assert
        assert manager.config.toggle_recording_key == 'Pause'
        assert manager.current_popup is None


class TestShowTimedMessage:
    """時限付きメッセージ表示のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }
        self.manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_success(self, mock_label_class, mock_toplevel_class):
        """正常系: メッセージ表示成功"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("テストタイトル", "テストメッセージ", 3000)

        # Assert
        mock_toplevel_class.assert_called_once_with(self.mock_master)
        mock_popup.title.assert_called_once_with("テストタイトル")
        mock_popup.attributes.assert_called_once_with('-topmost', True)
        mock_label_class.assert_called_once_with(mock_popup, text="テストメッセージ")
        mock_label.pack.assert_called_once_with(padx=20, pady=20)
        mock_popup.after.assert_called_once_with(3000, self.manager._destroy_popup)
        assert self.manager.current_popup == mock_popup

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_with_existing_popup(self, mock_label_class, mock_toplevel_class):
        """正常系: 既存のポップアップがある場合は破棄してから表示"""
        # Arrange
        existing_popup = Mock()
        self.manager.current_popup = existing_popup

        new_popup = Mock()
        mock_toplevel_class.return_value = new_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("新しいタイトル", "新しいメッセージ")

        # Assert
        existing_popup.destroy.assert_called_once()
        mock_toplevel_class.assert_called_once_with(self.mock_master)
        assert self.manager.current_popup == new_popup

    @patch('app.notification_manager.tk.Toplevel')
    def test_show_timed_message_with_existing_popup_tcl_error(self, mock_toplevel_class):
        """異常系: 既存ポップアップ破棄時のTclError"""
        # Arrange
        existing_popup = Mock()
        existing_popup.destroy.side_effect = tk.TclError("Invalid window")
        self.manager.current_popup = existing_popup

        new_popup = Mock()
        mock_toplevel_class.return_value = new_popup

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert - エラーが発生しても新しいポップアップは表示される
        existing_popup.destroy.assert_called_once()
        mock_toplevel_class.assert_called_once()

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_default_duration(self, mock_label_class, mock_toplevel_class):
        """正常系: デフォルト表示時間（2秒）"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert
        mock_popup.after.assert_called_once_with(2000, self.manager._destroy_popup)

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_custom_duration(self, mock_label_class, mock_toplevel_class):
        """正常系: カスタム表示時間"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ", 5000)

        # Assert
        mock_popup.after.assert_called_once_with(5000, self.manager._destroy_popup)

    @patch('app.notification_manager.tk.Toplevel')
    def test_show_timed_message_exception(self, mock_toplevel_class, caplog):
        """異常系: ポップアップ作成時の例外"""
        # Arrange
        caplog.set_level(logging.ERROR)
        mock_toplevel_class.side_effect = Exception("Toplevel creation error")

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert
        assert "通知中にエラーが発生しました" in caplog.text

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_empty_title(self, mock_label_class, mock_toplevel_class):
        """境界値: 空のタイトル"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("", "メッセージ")

        # Assert
        mock_popup.title.assert_called_once_with("")

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_empty_message(self, mock_label_class, mock_toplevel_class):
        """境界値: 空のメッセージ"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("タイトル", "")

        # Assert
        mock_label_class.assert_called_once_with(mock_popup, text="")

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_show_timed_message_long_text(self, mock_label_class, mock_toplevel_class):
        """境界値: 長いメッセージテキスト"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label
        long_message = "とても長いメッセージ" * 100

        # Act
        self.manager.show_timed_message("タイトル", long_message)

        # Assert
        mock_label_class.assert_called_once_with(mock_popup, text=long_message)


class TestDestroyPopup:
    """ポップアップ破棄のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }
        self.manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

    def test_destroy_popup_success(self):
        """正常系: ポップアップ破棄成功"""
        # Arrange
        mock_popup = Mock()
        self.manager.current_popup = mock_popup

        # Act
        self.manager._destroy_popup()

        # Assert
        mock_popup.destroy.assert_called_once()
        assert self.manager.current_popup is None

    def test_destroy_popup_no_popup(self):
        """境界値: ポップアップが存在しない場合"""
        # Arrange
        self.manager.current_popup = None

        # Act
        self.manager._destroy_popup()

        # Assert - エラーが発生しないことを確認
        assert self.manager.current_popup is None

    def test_destroy_popup_tcl_error(self):
        """異常系: TclError発生時"""
        # Arrange
        mock_popup = Mock()
        mock_popup.destroy.side_effect = tk.TclError("Invalid window")
        self.manager.current_popup = mock_popup

        # Act
        self.manager._destroy_popup()

        # Assert
        mock_popup.destroy.assert_called_once()
        assert self.manager.current_popup is None

    def test_destroy_popup_general_exception(self, caplog):
        """異常系: 一般的な例外発生時"""
        # Arrange
        caplog.set_level(logging.ERROR)
        mock_popup = Mock()
        mock_popup.destroy.side_effect = Exception("Unexpected error")
        self.manager.current_popup = mock_popup

        # Act
        self.manager._destroy_popup()

        # Assert
        assert "ポップアップ終了中にエラーが発生しました" in caplog.text
        assert self.manager.current_popup is None


class TestCleanup:
    """クリーンアップ処理のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }
        self.manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

    def test_cleanup_with_popup(self):
        """正常系: ポップアップありのクリーンアップ"""
        # Arrange
        mock_popup = Mock()
        self.manager.current_popup = mock_popup

        # Act
        self.manager.cleanup()

        # Assert
        mock_popup.destroy.assert_called_once()

    def test_cleanup_without_popup(self):
        """境界値: ポップアップなしのクリーンアップ"""
        # Arrange
        self.manager.current_popup = None

        # Act
        self.manager.cleanup()

        # Assert - エラーが発生しないことを確認

    def test_cleanup_tcl_error(self):
        """異常系: クリーンアップ時のTclError"""
        # Arrange
        mock_popup = Mock()
        mock_popup.destroy.side_effect = tk.TclError("Invalid window")
        self.manager.current_popup = mock_popup

        # Act
        self.manager.cleanup()

        # Assert - エラーが発生しても処理は継続
        mock_popup.destroy.assert_called_once()


class TestIntegrationScenarios:
    """統合シナリオテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_multiple_notifications_workflow(self, mock_label_class, mock_toplevel_class):
        """統合テスト: 複数の通知を順次表示"""
        # Arrange
        manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

        popup1 = Mock()
        popup2 = Mock()
        popup3 = Mock()
        mock_toplevel_class.side_effect = [popup1, popup2, popup3]

        mock_label1 = Mock()
        mock_label2 = Mock()
        mock_label3 = Mock()
        mock_label_class.side_effect = [mock_label1, mock_label2, mock_label3]

        # Act
        manager.show_timed_message("通知1", "メッセージ1", 1000)
        assert manager.current_popup == popup1

        manager.show_timed_message("通知2", "メッセージ2")
        popup1.destroy.assert_called_once()
        assert manager.current_popup == popup2

        manager.show_timed_message("通知3", "メッセージ3", 3000)
        popup2.destroy.assert_called_once()
        assert manager.current_popup == popup3

        # クリーンアップ
        manager.cleanup()
        popup3.destroy.assert_called_once()


class TestEdgeCases:
    """エッジケーステスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }
        self.manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_notification_with_special_characters(self, mock_label_class, mock_toplevel_class):
        """エッジケース: 特殊文字を含む通知"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        special_text = "改行\n\tタブ\r\n特殊文字!@#$%^&*()"

        # Act
        self.manager.show_timed_message("特殊文字", special_text)

        # Assert
        mock_label_class.assert_called_once_with(mock_popup, text=special_text)

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_notification_with_unicode(self, mock_label_class, mock_toplevel_class):
        """エッジケース: Unicode文字を含む通知"""
        # Arrange
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        unicode_text = "日本語🎉한글Émojis"

        # Act
        self.manager.show_timed_message("Unicode", unicode_text)

        # Assert
        mock_label_class.assert_called_once_with(mock_popup, text=unicode_text)

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_rapid_notifications(self, mock_label_class, mock_toplevel_class):
        """エッジケース: 短時間に大量の通知"""
        # Arrange
        popups = [Mock() for _ in range(10)]
        labels = [Mock() for _ in range(10)]
        mock_toplevel_class.side_effect = popups
        mock_label_class.side_effect = labels

        # Act
        for i in range(10):
            self.manager.show_timed_message(f"通知{i}", f"メッセージ{i}")

        # Assert
        assert mock_toplevel_class.call_count == 10
        assert self.manager.current_popup == popups[-1]

    def test_cleanup_multiple_times(self):
        """エッジケース: クリーンアップを複数回呼び出し"""
        # Arrange
        mock_popup = Mock()
        self.manager.current_popup = mock_popup

        # Act
        self.manager.cleanup()
        self.manager.cleanup()
        self.manager.cleanup()

        # Assert
        # cleanup()はcurrent_popupをNoneにしないため、毎回destroyが呼ばれる
        # ただし、実際のtkinterではエラーが発生する可能性があるため注意が必要
        assert mock_popup.destroy.call_count == 3


class TestErrorHandling:
    """エラーハンドリングの詳細テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.mock_master = Mock(spec=tk.Tk)
        self.mock_config = {
            'KEYS': {
                'TOGGLE_RECORDING': 'F1'
            }
        }
        self.manager = NotificationManager(self.mock_master, dict_to_app_config(self.mock_config))

    @patch('app.notification_manager.tk.Toplevel')
    def test_toplevel_creation_failure(self, mock_toplevel_class, caplog):
        """異常系: Toplevel作成失敗"""
        # Arrange
        caplog.set_level(logging.ERROR)
        mock_toplevel_class.side_effect = tk.TclError("Display error")

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert
        assert "通知中にエラーが発生しました" in caplog.text

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_label_creation_failure(self, mock_label_class, mock_toplevel_class, caplog):
        """異常系: Label作成失敗"""
        # Arrange
        caplog.set_level(logging.ERROR)
        mock_popup = Mock()
        mock_toplevel_class.return_value = mock_popup
        mock_label_class.side_effect = Exception("Label creation error")

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert
        assert "通知中にエラーが発生しました" in caplog.text

    @patch('app.notification_manager.tk.Toplevel')
    @patch('app.notification_manager.tk.Label')
    def test_after_scheduling_failure(self, mock_label_class, mock_toplevel_class, caplog):
        """異常系: afterスケジューリング失敗"""
        # Arrange
        caplog.set_level(logging.ERROR)
        mock_popup = Mock()
        mock_popup.after.side_effect = Exception("After error")
        mock_toplevel_class.return_value = mock_popup
        mock_label = Mock()
        mock_label_class.return_value = mock_label

        # Act
        self.manager.show_timed_message("タイトル", "メッセージ")

        # Assert
        assert "通知中にエラーが発生しました" in caplog.text
