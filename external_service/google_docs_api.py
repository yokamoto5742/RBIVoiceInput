import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build

from utils.app_config import AppConfig
from utils.env_loader import load_env_variables

DOCS_SCOPE = 'https://www.googleapis.com/auth/documents'
_DOC_ID_PATTERN = re.compile(r'/document/d/([a-zA-Z0-9_-]+)')


@dataclass
class GoogleDocsClient:
    service: object
    document_id: str


def extract_document_id(url: str) -> str:
    """Google Docs URLからdocumentIdを抽出する"""
    if not url:
        raise ValueError('Google DocsのURLが未設定です')
    match = _DOC_ID_PATTERN.search(url)
    if not match:
        raise ValueError(f'Google DocsのURLからIDを抽出できません: {url}')
    return match.group(1)


def _load_service_account_credentials(value: str) -> service_account.Credentials:
    stripped = value.strip()
    if stripped.startswith('{'):
        info = json.loads(stripped)
        return service_account.Credentials.from_service_account_info(
            info, scopes=[DOCS_SCOPE]
        )
    return service_account.Credentials.from_service_account_file(
        stripped, scopes=[DOCS_SCOPE]
    )


def setup_google_docs_client(config: AppConfig) -> Optional[GoogleDocsClient]:
    """Google Docsクライアントを構築する"""
    url = config.google_docs_url
    if not url:
        return None

    document_id = extract_document_id(url)

    env_vars = load_env_variables()
    credentials_value = env_vars.get('GOOGLE_CREDENTIALS_JSON')
    if not credentials_value:
        raise ValueError('GOOGLE_CREDENTIALS_JSONが未設定です')

    credentials = _load_service_account_credentials(credentials_value)
    service = build('docs', 'v1', credentials=credentials, cache_discovery=False)

    return GoogleDocsClient(service=service, document_id=document_id)


def _get_end_index(client: GoogleDocsClient) -> int:
    """ドキュメント本文末尾のendIndexを取得する"""
    document = client.service.documents().get(documentId=client.document_id).execute()  # 
    body_content = document.get('body', {}).get('content', [])
    if not body_content:
        return 1
    last_end = body_content[-1].get('endIndex', 1)
    # endIndexは末尾改行の次の位置を指すため挿入位置はその直前
    return max(1, last_end - 1)


def append_text(client: GoogleDocsClient, text: str) -> None:
    """ドキュメント末尾にテキストを追加する"""
    if not text:
        logging.warning('Docs追加: 空のテキスト')
        return

    insert_index = _get_end_index(client)
    requests = [{
        'insertText': {
            'location': {'index': insert_index},
            'text': text,
        }
    }]
    client.service.documents().batchUpdate(  # 
        documentId=client.document_id,
        body={'requests': requests},
    ).execute()
    logging.info(f'Docs追加完了: {len(text)}文字')


def insert_text_at_end(client: GoogleDocsClient, text: str) -> Tuple[int, int]:
    """ドキュメント末尾に挿入し、挿入範囲(start, end)を返す"""
    if not text:
        raise ValueError('挿入テキストが空です')

    insert_index = _get_end_index(client)
    requests = [{
        'insertText': {
            'location': {'index': insert_index},
            'text': text,
        }
    }]
    client.service.documents().batchUpdate(  # 
        documentId=client.document_id,
        body={'requests': requests},
    ).execute()
    return insert_index, insert_index + len(text)


def replace_range(
        client: GoogleDocsClient,
        start_index: int,
        end_index: int,
        text: str,
) -> None:
    """指定範囲を削除し、同じ位置にテキストを挿入する"""
    requests: List[dict[str, Any]] = [{
        'deleteContentRange': {
            'range': {'startIndex': start_index, 'endIndex': end_index},
        }
    }]
    if text:
        requests.append({
            'insertText': {
                'location': {'index': start_index},
                'text': text,
            }
        })
    client.service.documents().batchUpdate(  # 
        documentId=client.document_id,
        body={'requests': requests},
    ).execute()
    logging.info(f'Docs置換完了: {end_index - start_index}文字 -> {len(text)}文字')


def delete_range(client: GoogleDocsClient, start_index: int, end_index: int) -> None:
    """指定範囲を削除する"""
    if start_index >= end_index:
        return
    requests = [{
        'deleteContentRange': {
            'range': {'startIndex': start_index, 'endIndex': end_index},
        }
    }]
    client.service.documents().batchUpdate(  # 
        documentId=client.document_id,
        body={'requests': requests},
    ).execute()
    logging.info(f'Docs削除完了: {end_index - start_index}文字')
