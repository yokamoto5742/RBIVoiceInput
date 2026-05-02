import logging
import threading
from typing import Callable, Dict, Optional, Tuple

from external_service.google_docs_api import (
    GoogleDocsClient,
    append_text,
    delete_range,
    insert_text_at_end,
    replace_range,
)
from service.text_transformer import remove_ja_en_spaces, replace_text

class DocsOutput:
    """文字起こしテキストをGoogle Docs末尾へ追記する"""

    def __init__(
            self,
            client: Optional[GoogleDocsClient],
            replacements: Dict[str, str],
            error_callback: Callable[[str, str], None],
            placeholder_text: str = '音声入力中…(60秒以内)',
            placeholder_wait_timeout: int = 10,
    ):
        self._client = client
        self._replacements = replacements
        self._show_error = error_callback
        self._placeholder_text = placeholder_text
        self._placeholder_wait_timeout = placeholder_wait_timeout
        self._placeholder_range: Optional[Tuple[int, int]] = None
        self._placeholder_event = threading.Event()
        self._placeholder_event.set()
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return self._client is not None

    def show_placeholder(self) -> None:
        """別スレッドで「音声入力中」をドキュメント末尾に挿入する"""
        if self._client is None:
            return
        self._placeholder_event.clear()
        thread = threading.Thread(
            target=self._show_placeholder_in_thread,
            daemon=True,
            name='Docs-Placeholder-Thread',
        )
        thread.start()

    def _show_placeholder_in_thread(self) -> None:
        try:
            with self._lock:
                assert self._client is not None
                start, end = insert_text_at_end(self._client, self._placeholder_text)
                self._placeholder_range = (start, end)
        except Exception as e:
            logging.error(f'プレースホルダ挿入中にエラー: {type(e).__name__}: {str(e)}')
            self._placeholder_range = None
        finally:
            self._placeholder_event.set()

    def append(self, text: str) -> None:
        """別スレッドでGoogle Docsへ追記する。プレースホルダがあれば置換する"""
        if not text:
            return
        if self._client is None:
            self._show_error('エラー', 'Google DocsのURLが未設定です')
            return

        thread = threading.Thread(
            target=self._append_in_thread,
            args=(text,),
            daemon=True,
            name='Docs-Append-Thread',
        )
        thread.start()

    def _append_in_thread(self, text: str) -> None:
        try:
            transformed = remove_ja_en_spaces(replace_text(text, self._replacements))
            self._placeholder_event.wait(timeout=self._placeholder_wait_timeout)
            with self._lock:
                assert self._client is not None
                if not transformed:
                    logging.error('Docs追記: テキスト変換結果が空です')
                    self._delete_placeholder_locked()
                    return
                if self._placeholder_range is not None:
                    start, end = self._placeholder_range
                    replace_range(self._client, start, end, transformed)
                    self._placeholder_range = None
                else:
                    append_text(self._client, transformed)
        except Exception as e:
            logging.error(f'Docs追記中にエラー: {type(e).__name__}: {str(e)}')
            self._show_error('エラー', f'Docsへの追記に失敗しました: {str(e)}')

    def clear_placeholder(self) -> None:
        """エラー時などにプレースホルダのみを削除する"""
        if self._client is None:
            return
        thread = threading.Thread(
            target=self._clear_placeholder_in_thread,
            daemon=True,
            name='Docs-Placeholder-Clear-Thread',
        )
        thread.start()

    def _clear_placeholder_in_thread(self) -> None:
        try:
            self._placeholder_event.wait(timeout=self._placeholder_wait_timeout)
            with self._lock:
                self._delete_placeholder_locked()
        except Exception as e:
            logging.error(f'プレースホルダ削除中にエラー: {type(e).__name__}: {str(e)}')

    def _delete_placeholder_locked(self) -> None:
        if self._placeholder_range is None or self._client is None:
            return
        start, end = self._placeholder_range
        try:
            delete_range(self._client, start, end)
        finally:
            self._placeholder_range = None
