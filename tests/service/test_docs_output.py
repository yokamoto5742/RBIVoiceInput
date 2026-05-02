import threading
from unittest.mock import MagicMock, call, patch

import pytest

from external_service.google_docs_api import GoogleDocsClient
from service.docs_output import DocsOutput


def _make_client() -> GoogleDocsClient:
    service = MagicMock()
    documents = service.documents.return_value
    documents.get.return_value.execute.return_value = {
        'body': {'content': [{'endIndex': 10}]}
    }
    documents.batchUpdate.return_value.execute.return_value = {
        'replies': [{'insertText': {'startIndex': 9, 'endIndex': 12}}]
    }
    return GoogleDocsClient(service=service, document_id='doc123')


def _make_docs_output(
    client: GoogleDocsClient | None = None,
    placeholder_text: str = '音声入力中…',
    placeholder_wait_timeout: int = 1,
) -> DocsOutput:
    error_cb = MagicMock()
    return DocsOutput(
        client=client,
        replacements={},
        error_callback=error_cb,
        placeholder_text=placeholder_text,
        placeholder_wait_timeout=placeholder_wait_timeout,
    )


class TestDocsOutputIsAvailable:
    def test_available_with_client(self):
        output = _make_docs_output(client=_make_client())
        assert output.is_available() is True

    def test_unavailable_without_client(self):
        output = _make_docs_output(client=None)
        assert output.is_available() is False


class TestDocsOutputShowPlaceholder:
    def test_does_nothing_when_no_client(self):
        output = _make_docs_output(client=None)
        output.show_placeholder()
        assert output._placeholder_range is None

    def test_inserts_placeholder_text(self):
        client = _make_client()
        output = _make_docs_output(client=client, placeholder_text='入力中')
        output.show_placeholder()
        output._placeholder_event.wait(timeout=2.0)

        documents = client.service.documents.return_value
        documents.batchUpdate.assert_called_once()
        request = documents.batchUpdate.call_args.kwargs['body']['requests'][0]['insertText']
        assert request['text'] == '入力中'

    def test_placeholder_range_set_after_insert(self):
        client = _make_client()
        output = _make_docs_output(client=client)
        output.show_placeholder()
        output._placeholder_event.wait(timeout=2.0)
        assert output._placeholder_range is not None


class TestDocsOutputAppend:
    def test_shows_error_when_no_client(self):
        error_cb = MagicMock()
        output = DocsOutput(
            client=None,
            replacements={},
            error_callback=error_cb,
        )
        output.append('テスト')
        assert error_cb.called

    def test_does_nothing_on_empty_text(self):
        client = _make_client()
        output = _make_docs_output(client=client)
        output.append('')
        documents = client.service.documents.return_value
        documents.batchUpdate.assert_not_called()

    def test_appends_text_when_no_placeholder(self):
        client = _make_client()
        output = _make_docs_output(client=client)
        done = threading.Event()
        original_append = output._append_in_thread

        def _patched(text: str) -> None:
            original_append(text)
            done.set()

        output._append_in_thread = _patched
        output.append('こんにちは')
        done.wait(timeout=2.0)

        documents = client.service.documents.return_value
        documents.batchUpdate.assert_called_once()
        request = documents.batchUpdate.call_args.kwargs['body']['requests'][0]['insertText']
        assert request['text'] == 'こんにちは'

    def test_replaces_placeholder_when_present(self):
        client = _make_client()
        documents = client.service.documents.return_value

        output = _make_docs_output(client=client)
        output._placeholder_range = (5, 10)

        done = threading.Event()
        original = output._append_in_thread

        def _patched(text: str) -> None:
            original(text)
            done.set()

        output._append_in_thread = _patched
        output.append('置換テキスト')
        done.wait(timeout=2.0)

        assert output._placeholder_range is None
        call_args = documents.batchUpdate.call_args.kwargs['body']['requests']
        # replace_range は deleteContentRange + insertText の2リクエスト
        assert len(call_args) == 2


class TestDocsOutputClearPlaceholder:
    def test_does_nothing_when_no_client(self):
        output = _make_docs_output(client=None)
        output._placeholder_range = (1, 5)
        output.clear_placeholder()
        # クライアントなしなのでスレッドを起動しない
        assert output._placeholder_range == (1, 5)

    def test_deletes_placeholder_range(self):
        client = _make_client()
        output = _make_docs_output(client=client)
        output._placeholder_range = (3, 8)

        done = threading.Event()
        original = output._clear_placeholder_in_thread

        def _patched() -> None:
            original()
            done.set()

        output._clear_placeholder_in_thread = _patched
        output.clear_placeholder()
        done.wait(timeout=2.0)

        assert output._placeholder_range is None
        documents = client.service.documents.return_value
        documents.batchUpdate.assert_called_once()


class TestDocsOutputPlaceholderConfig:
    def test_custom_placeholder_text_used(self):
        client = _make_client()
        output = _make_docs_output(client=client, placeholder_text='カスタムテキスト')
        assert output._placeholder_text == 'カスタムテキスト'

    def test_custom_wait_timeout_used(self):
        output = _make_docs_output(client=None, placeholder_wait_timeout=5)
        assert output._placeholder_wait_timeout == 5

    def test_default_placeholder_text(self):
        output = DocsOutput(client=None, replacements={}, error_callback=MagicMock())
        assert output._placeholder_text == '音声入力中…(60秒以内)'

    def test_default_wait_timeout(self):
        output = DocsOutput(client=None, replacements={}, error_callback=MagicMock())
        assert output._placeholder_wait_timeout == 10
