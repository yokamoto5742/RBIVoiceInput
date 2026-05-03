import threading
from unittest.mock import MagicMock

from service.firestore_output import FirestoreOutput


def _make_output(client: MagicMock | None = None) -> tuple[FirestoreOutput, MagicMock]:
    error_cb = MagicMock()
    output = FirestoreOutput(
        client=client,
        room_id='room1',
        collection='rooms',
        ttl_minutes=10,
        replacements={},
        error_callback=error_cb,
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

    def test_appends_to_segments(self):
        client = MagicMock()
        output, _ = _make_output(client=client)
        done = _wait_for_thread(output, '_append_in_thread')

        output.append('こんにちは')
        done.wait(timeout=2.0)

        segments = (
            client.collection.return_value
            .document.return_value
            .collection.return_value
        )
        segments.add.assert_called_once()
        payload = segments.add.call_args.args[0]
        assert payload['text'] == 'こんにちは'
        assert payload['senderId'] == 'room1'
        assert 'createdAt' in payload
        assert 'expiresAt' in payload


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
        assert payload['senderId'] == 'room1'


class TestFirestoreOutputClearSegments:
    def test_shows_error_when_no_client(self):
        output, error_cb = _make_output(client=None)
        output.clear_segments()
        assert error_cb.called

    def test_deletes_all_segments(self):
        client = MagicMock()
        batch = client.batch.return_value
        doc1 = MagicMock()
        doc2 = MagicMock()
        segments = (
            client.collection.return_value
            .document.return_value
            .collection.return_value
        )
        segments.stream.return_value = [doc1, doc2]

        output, _ = _make_output(client=client)
        done = _wait_for_thread(output, '_clear_segments_in_thread')

        output.clear_segments()
        done.wait(timeout=2.0)

        assert batch.delete.call_count == 2
        batch.commit.assert_called()
