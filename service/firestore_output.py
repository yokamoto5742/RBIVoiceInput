import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from google.cloud import firestore

from service.text_transformer import remove_ja_en_spaces, replace_text


class FirestoreOutput:
    """文字起こしテキストを Firestore へ追記する"""

    def __init__(
            self,
            client: Optional[firestore.Client],
            room_id: str,
            collection: str,
            ttl_minutes: int,
            replacements: Dict[str, str],
            error_callback: Callable[[str, str], None],
    ):
        self._client = client
        self._room_id = room_id
        self._collection = collection
        self._ttl_minutes = ttl_minutes
        self._replacements = replacements
        self._show_error = error_callback

    def is_available(self) -> bool:
        return self._client is not None and bool(self._room_id)

    def _transcript_ref(self):
        assert self._client is not None
        return (
            self._client.collection(self._collection)
            .document(self._room_id)
            .collection('transcript')
            .document('body')
        )

    def _meta_ref(self):
        assert self._client is not None
        return (
            self._client.collection(self._collection)
            .document(self._room_id)
            .collection('meta')
            .document('state')
        )

    def append(self, text: str) -> None:
        """別スレッドで /rooms/{room_id}/transcript/body の text 末尾に連結する"""
        if not text:
            return
        if not self.is_available():
            self._show_error('エラー', 'Firestore が未設定です')
            return

        thread = threading.Thread(
            target=self._append_in_thread,
            args=(text,),
            daemon=True,
            name='Firestore-Append-Thread',
        )
        thread.start()

    def _append_in_thread(self, text: str) -> None:
        try:
            transformed = remove_ja_en_spaces(replace_text(text, self._replacements))
            if not transformed:
                logging.warning('Firestore追記: テキスト変換結果が空です')
                return

            chunk = transformed + '\n'
            ref = self._transcript_ref()
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=self._ttl_minutes)

            assert self._client is not None

            @firestore.transactional
            def txn(transaction: firestore.Transaction) -> None:
                snap = ref.get(transaction=transaction)
                current = snap.get('text') if snap.exists else ''
                new_text = (current or '') + chunk
                payload = {
                    'text': new_text,
                    'updatedAt': now,
                    'expiresAt': expires_at,
                }
                if snap.exists:
                    transaction.update(ref, payload)
                else:
                    transaction.set(ref, payload)

            txn(self._client.transaction())
            logging.info(f'Firestore追記完了: {len(chunk)}文字')
        except Exception as e:
            logging.error(f'Firestore追記中にエラー: {type(e).__name__}: {str(e)}')
            self._show_error('エラー', f'Firestoreへの追記に失敗しました: {str(e)}')

    def update_presence(self, recording: bool) -> None:
        """録音状態を /rooms/{room_id}/meta/state に書き込む"""
        if not self.is_available():
            return
        thread = threading.Thread(
            target=self._update_presence_in_thread,
            args=(recording,),
            daemon=True,
            name='Firestore-Presence-Thread',
        )
        thread.start()

    def _update_presence_in_thread(self, recording: bool) -> None:
        try:
            self._meta_ref().set(
                {
                    'recording': recording,
                    'lastPing': firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
        except Exception as e:
            logging.error(f'presence更新中にエラー: {type(e).__name__}: {str(e)}')
