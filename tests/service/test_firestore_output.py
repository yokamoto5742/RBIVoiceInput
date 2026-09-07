import threading
from unittest.mock import MagicMock, patch

from service.firestore_output import FirestoreOutput


def _make_ui_processor() -> MagicMock:
    """schedule_callback をその場で実行する UIQueueProcessor スタブ"""
    ui_processor = MagicMock()
    ui_processor.schedule_callback.side_effect = lambda cb, *args: cb(*args)
    return ui_processor


def _make_output(client: MagicMock | None = None) -> tuple[FirestoreOutput, MagicMock]:
    error_cb = MagicMock()
    output = FirestoreOutput(
        client=client,
        room_id='room1',
        collection='rooms',
        ttl_minutes=10,
        replacements={},
        error_callback=error_cb,
        ui_processor=_make_ui_processor(),
    )
    return output, error_cb


def _wait_for_thread(output: FirestoreOutput, method_name: str) -> threading.Event:
    """対象メソッドのラップで完了通知 Event を返す"""
    done = threading.Event()
    original = getattr(output, method_name)

    def wrapped(*args, **kwargs):
        original(*args, **kwargs)
        done.set()

    setattr(output, method_name, wrapped)
    return done


class TestFirestoreOutputAvailability:
    def test_available_with_client_and_room(self):
        output, _ = _make_output(client=MagicMock())
        assert output.is_available() is True

    def test_unavailable_without_client(self):
        output, _ = _make_output(client=None)
        assert output.is_available() is False

    def test_unavailable_without_room_id(self):
        client = MagicMock()
        output = FirestoreOutput(
            client=client, room_id='', collection='rooms',
            ttl_minutes=10, replacements={}, error_callback=MagicMock(),
            ui_processor=_make_ui_processor(),
        )
        assert output.is_available() is False


class TestFirestoreOutputAppend:
    def test_shows_error_when_no_client(self):
        output, error_cb = _make_output(client=None)
        output.append('テスト')
        assert error_cb.called

    def test_does_nothing_on_empty_text(self):
        client = MagicMock()
        output, _ = _make_output(client=client)
        output.append('')
        client.collection.assert_not_called()

    def test_appends_to_transcript_via_transaction(self):
        client = MagicMock()
        # transactional デコレータをパススルーにする
        with patch(
                'service.firestore_output.firestore.transactional',
                side_effect=lambda fn: fn,
        ):
            output, _ = _make_output(client=client)
            done = _wait_for_thread(output, '_append_in_thread')

            # 既存 doc なし → set 経路
            transcript_doc = (
                client.collection.return_value
                .document.return_value
                .collection.return_value
                .document.return_value
            )
            snap = transcript_doc.get.return_value
            snap.exists = False

            output.append('こんにちは')
            done.wait(timeout=2.0)

            transaction = client.transaction.return_value
            transaction.set.assert_called_once()
            ref_arg, payload = transaction.set.call_args.args
            assert ref_arg is transcript_doc
            assert payload['text'] == 'こんにちは\n'
            assert 'updatedAt' in payload
            assert 'expiresAt' in payload
            assert 'senderId' not in payload

    def test_appends_concatenates_existing_text(self):
        client = MagicMock()
        with patch(
                'service.firestore_output.firestore.transactional',
                side_effect=lambda fn: fn,
        ):
            output, _ = _make_output(client=client)
            done = _wait_for_thread(output, '_append_in_thread')

            transcript_doc = (
                client.collection.return_value
                .document.return_value
                .collection.return_value
                .document.return_value
            )
            snap = transcript_doc.get.return_value
            snap.exists = True
            snap.get.return_value = '既存テキスト\n'

            output.append('追加')
            done.wait(timeout=2.0)

            transaction = client.transaction.return_value
            transaction.update.assert_called_once()
            _, payload = transaction.update.call_args.args
            assert payload['text'] == '既存テキスト\n追加\n'


class TestFirestoreOutputErrorNotification:
    def test_worker_thread_error_goes_through_ui_processor(self):
        """ワーカースレッドのエラー通知は UIQueueProcessor 経由で行われる"""
        client = MagicMock()
        error_cb = MagicMock()
        ui_processor = MagicMock()
        output = FirestoreOutput(
            client=client, room_id='room1', collection='rooms',
            ttl_minutes=10, replacements={}, error_callback=error_cb,
            ui_processor=ui_processor,
        )
        client.transaction.side_effect = RuntimeError('接続失敗')
        done = _wait_for_thread(output, '_append_in_thread')

        output.append('テスト')
        done.wait(timeout=2.0)

        # error_callback を直接呼ばず、キュー経由で委譲していること
        error_cb.assert_not_called()
        ui_processor.schedule_callback.assert_called_once()
        callback, title, message = ui_processor.schedule_callback.call_args.args
        assert callback is error_cb
        assert title == 'エラー'
        assert 'Firestoreへの追記に失敗しました' in message


class TestFirestoreOutputUpdatePresence:
    def test_skipped_without_client(self):
        output, _ = _make_output(client=None)
        output.update_presence(True)  # 例外なし

    def test_writes_presence(self):
        client = MagicMock()
        output, _ = _make_output(client=client)
        done = _wait_for_thread(output, '_update_presence_in_thread')

        output.update_presence(True)
        done.wait(timeout=2.0)

        meta = (
            client.collection.return_value
            .document.return_value
            .collection.return_value
            .document.return_value
        )
        meta.set.assert_called_once()
        payload = meta.set.call_args.args[0]
        assert payload['recording'] is True
        assert 'lastPing' in payload
        assert 'senderId' not in payload
