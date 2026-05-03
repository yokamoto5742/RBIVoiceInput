# RBIVoiceInput リファクタリングプラン

## 目的

文字起こし結果の出力先を **Google Docs → Firestore** に切り替える。
Google Docs 関連コードは完全に削除する。

## 構成変更

### 削除対象

- `external_service/google_docs_api.py`
- `service/docs_output.py`
- `app/replacements_editor.py` 内の Docs URL 関連 UI（必要箇所のみ）
- `AppConfig` の `google_docs_url` / `google_docs_placeholder_text` / `google_docs_placeholder_wait_timeout`
- `config.ini` の `[GOOGLE_DOCS]` セクション
- 依存パッケージ：`google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`（Docs用に入っているもの）

### 新規追加

- `external_service/firestore_api.py` — Firestore クライアント初期化（サービスアカウント）
- `service/firestore_output.py` — `DocsOutput` 相当の Firestore 版
- `config.ini` に `[FIRESTORE]` セクション追加

## config.ini 変更

```ini
[FIRESTORE]
PROJECT_ID = your-firebase-project-id
ROOM_ID = tanaka-pc          ; 手動採番、1端末1固定
COLLECTION = rooms           ; /rooms/{ROOM_ID}/segments
TTL_MINUTES = 10
VIEWER_BASE_URL = https://rbivoice.example.com
```

`.env` に `FIREBASE_CREDENTIALS_JSON`（サービスアカウントキーのパス or JSON 文字列）を追加。
既存の `GOOGLE_CREDENTIALS_JSON` を STT 用と Firestore 用で共用

## 依存追加

```
google-cloud-firestore
```

`uv add google-cloud-firestore`

## 実装詳細

### `external_service/firestore_api.py`

```python
from google.cloud import firestore

def setup_firestore_client(config: AppConfig) -> firestore.Client:
    """サービスアカウントで Firestore クライアントを初期化"""
```

- `GOOGLE_APPLICATION_CREDENTIALS` 経由で認証。
- `project=config.firestore_project_id` を明示。

### `service/firestore_output.py`

```python
class FirestoreOutput:
    def __init__(self, client, room_id: str, collection: str,
                 ttl_minutes: int, replacements: dict[str, str],
                 error_callback: Callable[[str, str], None]):
        ...

    def is_available(self) -> bool: ...
    def append(self, text: str) -> None:
        """別スレッドで /rooms/{room_id}/segments に追記"""
```

ドキュメント形式：

```json
{
  "text": "変換後テキスト",
  "createdAt": <serverTimestamp>,
  "expiresAt": <createdAt + ttl_minutes>,
  "senderId": "<config.room_id>"
}
```

- `expiresAt` フィールドは Firestore TTL ポリシーで自動削除対象（コンソールで設定）。
- `text_transformer.replace_text` + `remove_ja_en_spaces` を `append()` 内で適用（既存ロジック流用）。
- プレースホルダ機能は不要（Firestore は追記のみ。Viewer 側で「録音中」表示は presence で実装）。

### presence（録音状態の通知）

- `start_recording()` 時に `/rooms/{roomId}/meta` の `recording=true, lastPing=now` を更新。
- `RecordingTimer` のチック中、定期的に `lastPing` を更新（10秒間隔）。
- `stop_recording()` で `recording=false` に。
- これにより Viewer 側で「録音中／待機中／切断」表示が可能。

### 手動クリア

- 既存 UI に「Webクリア」ボタンを追加。
- `/rooms/{roomId}/segments` の全ドキュメントを削除（バッチ削除）。
- ボタンは PC 側のみ有効（Web 側のクリアはローカル表示のみ、と Viewer 側で実装）。

## 変更が必要な既存ファイル

| ファイル | 変更内容 |
|---|---|
| `app/application.py` | `setup_google_docs_client` / `DocsOutput` を `setup_firestore_client` / `FirestoreOutput` に置換 |
| `service/recording_lifecycle.py` | `docs_output` を `firestore_output` にリネーム、`show_placeholder` / `clear_placeholder` 呼び出しを削除、presence 更新呼び出し追加 |
| `utils/app_config.py` | `[GOOGLE_DOCS]` プロパティ削除、`[FIRESTORE]` プロパティ追加（`firestore_project_id`, `room_id`, `firestore_collection`, `firestore_ttl_minutes`, `viewer_base_url`） |
| `app/main_window.py` | Docs URL 表示を Viewer URL（`{viewer_base_url}/?room={room_id}`）に変更、Webクリアボタン追加 |
| `constants.py`（既存があれば） | UI 文言追加：「Webクリア」「録音中（配信中）」等 |
| `tests/` | `test_docs_output.py` を `test_firestore_output.py` に置換（`pytest-mock` で Firestore クライアントをモック） |
| `pyproject.toml` | 依存差し替え |

## 作業順序

1. `google-cloud-firestore` を追加、Firebase プロジェクト作成、サービスアカウントキー取得
2. `firestore_api.py` / `firestore_output.py` を新規作成（テスト含む）
3. `AppConfig` に `[FIRESTORE]` プロパティ追加
4. `application.py` で `FirestoreOutput` を配線（Docs と並行で動作確認）
5. `recording_lifecycle.py` を Firestore 専用に変更
6. presence 更新ロジック実装
7. `main_window.py` の UI 文言変更、Webクリアボタン追加
8. Docs 関連コード・設定・依存を削除
9. `pyright app service utils` で型チェック
10. `python -m pytest tests/ -v` で回帰確認
11. `python build.py` で exe ビルド確認

## セキュリティ

- サービスアカウントキーは `.env` 経由でのみ読む。リポジトリにコミットしない。
- Firestore セキュリティルールで「サービスアカウント以外の write を拒否」する（RBIVoice 側プランで詳述）。
- Sender 側は App Check 不要（サービスアカウント認証で十分）。

## 動作確認チェックリスト

- [ ] config.ini の `ROOM_ID` を変えると別 Viewer に振り分けられる
- [ ] 文字起こし結果が `replacements.txt` 適用後に Firestore に書かれる
- [ ] 10分経過で Firestore TTL によりドキュメントが消える
- [ ] PC 側「Webクリア」ボタンで即座に segments が空になる
- [ ] PC 側を落とすと Viewer に「切断」表示が出る（presence）
- [ ] 60秒自動停止後も presence が `recording=false` になる
