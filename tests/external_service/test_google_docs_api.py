from unittest.mock import MagicMock

import pytest

from external_service.google_docs_api import (
    GoogleDocsClient,
    append_text,
    extract_document_id,
)


class TestExtractDocumentId:
    def test_standard_url(self):
        url = 'https://docs.google.com/document/d/10whwZzYqdhE0hJadehajaJGypAdr0ulKG0Pzm7FPuC0/edit?usp=sharing'
        assert extract_document_id(url) == '10whwZzYqdhE0hJadehajaJGypAdr0ulKG0Pzm7FPuC0'

    def test_empty_url(self):
        with pytest.raises(ValueError):
            extract_document_id('')

    def test_invalid_url(self):
        with pytest.raises(ValueError):
            extract_document_id('https://example.com/no-doc-id')


class TestAppendText:
    def _make_client(self, end_index: int = 25) -> tuple[GoogleDocsClient, MagicMock, MagicMock]:
        service = MagicMock()
        documents = service.documents.return_value
        documents.get.return_value.execute.return_value = {
            'body': {'content': [{'endIndex': end_index}]}
        }
        batch = documents.batchUpdate.return_value
        batch.execute.return_value = {}
        client = GoogleDocsClient(service=service, document_id='doc123')
        return client, documents, batch

    def test_append_inserts_at_end(self):
        client, documents, _ = self._make_client(end_index=25)
        append_text(client, 'こんにちは')

        documents.batchUpdate.assert_called_once()
        kwargs = documents.batchUpdate.call_args.kwargs
        assert kwargs['documentId'] == 'doc123'
        request = kwargs['body']['requests'][0]['insertText']
        assert request['text'] == 'こんにちは'
        assert request['location']['index'] == 24

    def test_empty_text_skipped(self):
        client, documents, _ = self._make_client()
        append_text(client, '')
        documents.batchUpdate.assert_not_called()

    def test_empty_body(self):
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = {'body': {}}
        client = GoogleDocsClient(service=service, document_id='doc123')
        append_text(client, 'X')
        kwargs = service.documents.return_value.batchUpdate.call_args.kwargs
        assert kwargs['body']['requests'][0]['insertText']['location']['index'] == 1
