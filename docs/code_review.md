# コードレビュー: RBIVoiceInput

レビュー日: 2026-09-07 / 対象コミット: `a068e75` / 観点: 可読性・メンテナンス性・KISS

**検証済みのベースライン**

| 項目 | 結果 |
|---|---|
| `pytest tests/` | 264 passed (3.26s) |
| `pyright app service utils external_service` | 0 errors, 0 warnings |
| 本体コード行数 | 約 1,450 行 (テスト除く) |

型チェックとテストは緑です。以下の指摘は「動くが壊れやすい/読みにくい」箇所に集中しています。

---

## 総評

レイヤ分割（`app` / `service` / `external_service` / `utils`）は明確で、`AppConfig` によるファサード、`UIQueueProcessor` によるスレッド境界の明示など、設計の骨格は良好です。関数も概ね 50 行以内に収まっています。

一方で **「UI スレッド境界のルールが一部で破られている」** ことと、**「同じ状態・同じ文字列が複数箇所に複製されている」** ことが、可読性とメンテナンス性の主要なボトルネックになっています。特に `UIQueueProcessor` を用意しているのに Firestore ワーカースレッドがそれを迂回して Tk を直接叩いている点（H1）と、クリップボードをモジュール間 IPC に使っている点（H2）は、設計意図が読み手に伝わらなくなる原因です。

また、`../CLAUDE.md` が要求する `constants.py` が **存在しません**。UI 文字列は全てインライン定義です（M1）。

---

## 重大度: 高

### H1. Firestore ワーカースレッドから Tk ウィジェットを直接生成している

`service/firestore_output.py:100` のエラー通知は `Firestore-Append-Thread` 上で実行されますが、
`_show_error` の実体は `NotificationManager.show_timed_message`（`app/notification_manager.py:14`）で、
**非メインスレッドから `tk.Toplevel` を生成**しています。Tk はスレッドセーフではなく、
`RuntimeError: main thread is not in main loop` やハングの原因になります。

`UIQueueProcessor` はまさにこのために存在するので、それを経由させます。

```diff
--- a/service/firestore_output.py
+++ b/service/firestore_output.py
@@
 class FirestoreOutput:
     def __init__(
             self,
             client: Optional[firestore.Client],
             room_id: str,
             collection: str,
             ttl_minutes: int,
             replacements: Dict[str, str],
             error_callback: Callable[[str, str], None],
+            ui_processor: UIQueueProcessor,
     ):
@@
+        self._ui_processor = ui_processor
+
+    def _notify_error(self, message: str) -> None:
+        """ワーカースレッドからの通知を Tk メインスレッドへ委譲する"""
+        self._ui_processor.schedule_callback(self._show_error, 'エラー', message)
@@
         except Exception as e:
             logging.error(f'Firestore追記中にエラー: {type(e).__name__}: {str(e)}')
-            self._show_error('エラー', f'Firestoreへの追記に失敗しました: {str(e)}')
+            self._notify_error(f'Firestoreへの追記に失敗しました: {str(e)}')
```

> 補足: `append()` の冒頭（`firestore_output.py:56`）の `_show_error` はメインスレッドから呼ばれるため
> 現状問題ありませんが、呼び出し元が変わっても壊れないよう `_notify_error` に統一するのが安全です。

---

### H2. クリップボードをモジュール間の IPC に使っており、ユーザーのクリップボードを破壊する

```
UIComponents.reload_latest_audio (app/ui_components.py:131-133)
  → clipboard_clear() / clipboard_append(path) / event_generate('<<LoadAudioFile>>')
RecordingLifecycle.handle_audio_file (service/recording_lifecycle.py:188)
  → self.master.clipboard_get()
```

音声入力ツールという性質上、ユーザーはクリップボードを常用しています。
**ファイルパスを渡すためだけにユーザーのコピー内容を消す**のは副作用として重すぎます。
加えて、この経路は grep しても繋がりが見えず、読み手が追跡できません。

コールバックで直接パスを渡せば、仮想イベント・クリップボード操作・`<<LoadAudioFile>>` バインドの
3 つがまとめて不要になります。

```diff
--- a/app/ui_components.py
+++ b/app/ui_components.py
     def reload_latest_audio(self) -> None:
         latest_file = self.get_latest_audio_file()
-        if latest_file:
-            self.master.clipboard_clear()
-            self.master.clipboard_append(latest_file)
-            self.master.event_generate('<<LoadAudioFile>>')
-        else:
-            messagebox.showwarning('警告', '音声ファイルが見つかりません')
+        if not latest_file:
+            messagebox.showwarning('警告', MSG_AUDIO_FILE_NOT_FOUND)
+            return
+        self._on_audio_file_selected(latest_file)

     def open_audio_file(self) -> None:
         file_path = filedialog.askopenfilename(...)
         if file_path:
-            self.master.clipboard_clear()
-            self.master.clipboard_append(file_path)
-            self.master.event_generate('<<LoadAudioFile>>')
+            self._on_audio_file_selected(file_path)
```

```diff
--- a/service/recording_lifecycle.py
+++ b/service/recording_lifecycle.py
-    def handle_audio_file(self, event: Any) -> None:
-        """クリップボードから音声ファイルパスを取得して文字起こしする"""
-        try:
-            file_path = self.master.clipboard_get()
-            if not os.path.exists(file_path):
+    def handle_audio_file(self, file_path: str) -> None:
+        """指定された音声ファイルを文字起こしする"""
+        try:
+            if not os.path.exists(file_path):
```

`app/main_window.py:59` の `self.master.bind('<<LoadAudioFile>>', ...)` も削除できます。

---

### H3. `handle_audio_file` が UI スレッドで同期的に STT を呼び、UI がフリーズする

`service/recording_lifecycle.py:185-205` は `transcription_handler.handle_audio_file()` を
**メインスレッドで直接**実行します。録音経路（`_stop_recording_process`, 同 152 行）が
きちんとスレッド化されているのと非対称です。API 応答が返るまでウィンドウが無反応になります。

さらに、同じ関数の `finally`（同 203 行）でステータスラベルを即座に戻しているため、
`'音声ファイル処理中...'`（同 193 行）は **Tk が再描画する隙がなく一度も画面に出ません**。
つまりこの 2 行は現状ノーオペです。

録音経路と同じくワーカースレッド + `ui_processor.schedule_callback` に揃えるべきです。

---

### H4. `cleanup()` の順序が逆で、終了時の後処理が無効化される

`service/recording_lifecycle.py:254-282`:

```
260: self.ui_processor.shutdown()      # ← is_ui_valid() が以降 False を返す
263: if self.recorder.is_recording:
264:     self.stop_recording()          # → _stop_recording_process()
```

`shutdown()` 後は `is_ui_valid()` が常に `False` を返すため、`_stop_recording_process` 内の
`master.after(100, self._check_process_thread, ...)`（同 159-164 行）は登録されません。
にもかかわらず、その直前で**新しい文字起こしスレッドを起動**しています（同 152 行）。

現状は直前の `transcription_handler.cancel()`（同 261 行）のおかげで、
そのスレッドが `transcribe_frames` の冒頭でキャンセル判定して即 return するため実害は出ていません。
つまり **「たまたま動いている」状態** で、3 つの呼び出し順に暗黙的に依存しています。

意図を明示する順序に変更してください。

```diff
     def cleanup(self) -> None:
         try:
             logging.info('RecordingLifecycle クリーンアップ開始')
+            self.transcription_handler.cancel()
             self._stop_presence_ping()
             self.firestore_output.update_presence(False)
-            self.ui_processor.shutdown()
-            self.transcription_handler.cancel()
 
             if self.recorder.is_recording:
-                self.stop_recording()
+                self.recording_timer.cancel()
+                self.recorder.stop_recording()   # 文字起こしは開始しない
+
+            self.ui_processor.shutdown()
```

---

### H5. WAV 保存のたびに PyAudio インスタンスを生成し `terminate()` していない

`service/audio_file_manager.py:30`:

```python
wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
```

`pyaudio.PyAudio()` は PortAudio を初期化します。これを録音のたびに生成して破棄しないため、
リソースがリークします。`get_sample_size` は **モジュールレベル関数として利用可能**です（検証済み: `pyaudio.get_sample_size(pyaudio.paInt16) == 2`）。

```diff
-                wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
+                wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
```

---

### H6. `auto_stop_timer < 5` で `after()` に負のディレイが渡る

`service/recording_timer.py:40-43`:

```python
self._five_second_timer = self.master.after((auto_stop_timer - 5) * 1000, ...)
```

設定値が 5 秒未満だと負値になります。`max(0, ...)` でガードするか、
`5` を定数化した上で「auto_stop_timer が閾値以下なら事前通知しない」と明示してください。

---

### H7. 句読点フラグの実体が 4 箇所に複製されている

| 保持場所 | 参照 |
|---|---|
| `AppConfig.use_punctuation` (`utils/app_config.py:89`) | 設定ファイル（永続化） |
| `RecordingLifecycle._use_punctuation` (`service/recording_lifecycle.py:42`) | property + setter |
| `TranscriptionHandler.use_punctuation` (`service/transcription_handler.py:27`) | 実際に処理で使う値 |
| `UIComponents.punctuation_status_label` のテキスト | 表示 |

`app/main_window.py:64-71` の `toggle_punctuation` がこの 4 つを手動で同期しています。
1 箇所でも更新漏れがあれば表示と挙動がずれます。

`AppConfig` を単一の真実の源とし、`RecordingLifecycle` の property を廃止して
`TranscriptionHandler` が読み出し時に `config.use_punctuation` を参照する形が最もシンプルです。

なお `AppConfig.use_comma` は **書き込まれるだけで一度も読まれていません**（`main_window.py:70` のみ）。
実質デッドな状態を同期しているので、削除候補です。

---

## 重大度: 中

### M1. `constants.py` が存在せず、規約違反のまま UI 文字列が散在している

`../CLAUDE.md` / `../.claude/rules/python-coding.md` は明示的にこう定めています:

> UI 画面で表示するメッセージはすべて日本語にする / `constants.py` で一元管理し、マジック文字列を使わず必ず定数を参照する

実際には `constants.py` はプロジェクトに存在しません。特に複製が目立つもの:

| 文字列 | 出現箇所 |
|---|---|
| `f'{key}キーで音声入力開始/停止'` | `notification_manager.py:42`, `ui_components.py:103`, `recording_lifecycle.py:73`, `:174`, `:204` — **5 箇所** |
| `f'【現在句読点{"あり】" if … else "なし】"}'` | `ui_components.py:57`, `:121` — **2 箇所**（完全同一式） |
| `'テキスト出力中...'` | `recording_lifecycle.py:150`, `:179` |
| `'エラー'` (通知タイトル) | 各所 |

最低限、アイドル時ステータス文字列は関数化すべきです。

```python
# constants.py
MSG_IDLE_STATUS = '{key}キーで音声入力開始/停止'
MSG_RECORDING = '音声入力中... ({key}キーで停止)'
MSG_TRANSCRIBING = 'テキスト出力中...'
MSG_PUNCTUATION_ON = '【現在句読点あり】'
MSG_PUNCTUATION_OFF = '【現在句読点なし】'
MSG_AUDIO_FILE_NOT_FOUND = '音声ファイルが見つかりません'
TITLE_ERROR = 'エラー'
```

`ui_components.py:57` と `:121` は同一式なので、`setup_ui` から `update_punctuation_button()` を呼ぶだけで重複が消えます。

---

### M2. `_load_service_account_credentials` が 2 ファイルに完全重複

`external_service/google_stt_api.py:52-57` と `external_service/firestore_api.py:12-17` が
**1 文字違わず同一**です。`../utils` か `external_service/_credentials.py` に集約してください。

---

### M3. `load_env_variables()` が起動時に 2 回呼ばれる

`setup_google_stt_client`（`google_stt_api.py:61`）と `setup_firestore_client`（`firestore_api.py:27`）が
それぞれ独立して呼び出します。結果として `../.env` の読み込み・`_resolve_env_path()` のコピー処理・
未検出時の警告出力とエクスプローラ起動（`env_loader.py:37-42, 60-61`）が **2 回**走ります。

`Application.run()` で 1 度だけ読み、両クライアントに渡すのが素直です。

---

### M4. `UIComponents.update_callbacks` は完全に不要

`app/main_window.py:30-43` は、コールバック辞書を渡して `setup_ui()` した直後に
ほぼ同じ辞書で `update_callbacks()` を呼び直しています。この二段構えは
`'reload_audio': self.ui_components.reload_latest_audio` を後から差し込むためのものですが、

- `reload_audio` キーは **どこからも参照されていません**（ボタンは `ui_components.py:64` で
  `command=self.reload_latest_audio` と自身のメソッドを直接指しています）
- `toggle_recording` / `toggle_punctuation` / `hide_window` は `setup_ui` 時点で確定済み

つまり `update_callbacks()`（`ui_components.py:107-110`）と `main_window.py:38-43` の 6 行は
**まるごと削除できます**。

---

### M5. `_ui_callbacks` の文字列キー辞書は型安全でない

`service/recording_lifecycle.py:40, 62-65` の `Dict[str, Callable]` は 5 箇所で
`self._ui_callbacks['update_status_label'](...)` のように文字列添字でアクセスされます。
`wire_ui_callbacks()` が呼ばれる前に何かが走れば `KeyError` になり、
IDE 補完も型チェックも効きません。素直に属性にしてください。

```diff
-        self._ui_callbacks: Dict[str, Callable] = {}
+        self._update_record_button: Callable[[bool], Any] = lambda _: None
+        self._update_status_label: Callable[[str], Any] = lambda _: None
```

---

### M6. ウィジェットの None チェックに `assert` を使っている

`app/ui_components.py:113, 119, 125` の `assert self.record_button is not None` は
`python -O` で除去されます。そもそも `setup_ui()` を `__init__` に統合してウィジェットを
非 Optional にすれば、`Optional[tk.Button]` 宣言 9 個（同 24-32 行）と assert が同時に消えます。

---

### M7. `NotificationManager._update_status_label` は呼ばれても機能しない

`app/notification_manager.py:59`:

```python
status_label = self.master.children.get('status_label')
```

`UIComponents` は `tk.Label(self.master, ...)`（`ui_components.py:101`）と生成しており、
**`name='status_label'` を指定していません**。Tk の自動採番名（`!label` 等）になるため、
このルックアップは常に `None` を返します。

呼び出し元の `show_status_message` 自体も本番コードから参照されていない（テストのみ）ため、
`show_status_message` / `_update_status_label` はまとめて削除が妥当です。

---

### M8. 例外処理が過剰で、実際のロジックが埋もれている

`../.claude/rules/coding-guidelines.md` の「あり得ないシナリオに対するエラーハンドリングをしない」に反する箇所:

**(a) `service/text_transformer.py:6-18`** — `str.replace()` 2 回のために `except (AttributeError, TypeError)` と
`except Exception` の 2 段構え。`use_punctuation` が False の場合の 3 行に対して過剰です。

```diff
 def process_punctuation(text: str, use_punctuation: bool) -> str:
     """句読点の有無に応じてテキストを処理する"""
     if use_punctuation:
         return text
-
-    try:
-        return text.replace('。', '').replace('、', '')
-    except (AttributeError, TypeError) as e:
-        logging.error(f'句読点処理中にタイプエラー: {str(e)}')
-        return text
-    except Exception as e:
-        logging.error(f'句読点処理中に予期しないエラー: {str(e)}')
-        return text
+    return text.replace('。', '').replace('、', '')
```

**(b) `app/ui_queue_processor.py:60`** — `except (tk.TclError, Exception)` は
`Exception` が `TclError` を包含するため冗長。`except Exception` で同義です。

**(c) `service/keyboard_handler.py:61-83`** — 4 つのハンドラが
`try: self.master.after(0, cb) / except: log` という同一構造の 6 行 × 4。1 つの
ヘルパー `_dispatch(cb, label)` に畳めます。

---

### M9. `transcribe_pcm` の戻り値が三値（`None` / `''` / `str`）

`external_service/google_stt_api.py:144-190` は、エラー時 `None`、認識結果ゼロ件時 `''` を返します。
しかし呼び出し側（`transcription_handler.py:67`）は `if not transcription:` で両者を同一に扱い、
「文字起こしに失敗しました」という単一メッセージに潰しています。

「無音だった」と「API がエラーだった」はユーザーへの伝え方が変わるはずなので、
区別しないなら `''` に統一、区別するなら呼び出し側で分岐してください。現状は
**戻り値の型が語る契約と実際の扱いが食い違っています**。

---

### M10. `Application.run()` が 55 行の手続き的な組み立てコード

`app/application.py:27-87` は、設定読込・ロガー初期化・6 つのサービス生成・
UI 構築・mainloop 開始を 1 メソッドで行っています。50 行ガイドラインの境界上です。

`_build_services(config)` と `_build_ui(config, services)` の 2 段に割ると、
依存グラフが読み手に伝わりやすくなります。

---

### M11. `AudioRecorder` の録音状態が 3 つの変数に分散している

`is_recording` (bool) / `_stop_event` (Event) / `stream` (None かどうか) の 3 つが
同じ「録音中か」を別々に表現しています。加えて `start_recording`（`service/audio_recorder.py:27-42`）は
**`try` の外で `is_recording = True` を立てる**ため、マイクの `open()` に失敗しても
`is_recording` が True のまま残ります。

現状は `_safe_record` → `_safe_error_handler` → `_handle_error` の経路で復旧しますが、
3 モジュールを跨ぐ回復パスに依存しているのは脆いです。`open()` 成功後にフラグを立ててください。

```diff
     def start_recording(self) -> None:
         self._stop_event.clear()
-        self.is_recording = True
         self.frames = []
         try:
             self.p = pyaudio.PyAudio()
             self.stream = self.p.open(...)
+            self.is_recording = True
             self.logger.info('音声入力を開始しました。')
         except Exception as e:
             self.logger.error(f'音声入力の開始中に予期せぬエラーが発生しました: {e}')
```

また `stop_recording` は `self.p.terminate()` 後も `self.p` を `None` にしないため、
二重呼び出しで PortAudio を二度 terminate します。

---

### M12. ロギング層だけ `AppConfig` ファサードを迂回している

`app/application.py:30-31` は `setup_logging(config.raw_config)` と生の `ConfigParser` を渡します。
`AppConfig` を「設定への型安全な唯一の窓口」と位置づけている（`app_config.py:9` の docstring）以上、
`log_directory` / `log_level` / `debug_mode` 等も `AppConfig` のプロパティにすべきです。

併せて `../utils/log_rotation.py` の `config=None` → `load_config()` フォールバック
（10-12, 94-96, 130-132 行）は、本番の呼び出し元が常に config を渡すため未使用パスです。

---

### M13. `../main.py` の 3 つの `except` がほぼ同一構造

`main.py:16-33` は「メッセージ整形 → `logging.error` → `logging.debug(format_exc)` →
`show_error_dialog`」という同じ 4 ステップを 3 回書いています。テーブル駆動にすると 1/3 になります。

```python
ERROR_HANDLERS = {
    FileNotFoundError: ('ファイルエラー', '必要なファイルが見つかりません'),
    ValueError: ('設定エラー', '設定値エラー'),
}
```

---

### M14. `setup_logging` がハンドラを無条件に追加する

`utils/log_rotation.py:49, 54` は `root_logger.addHandler(...)` を毎回追加します。
テストや再初期化で 2 回呼ばれるとログが二重出力されます。冒頭で
`root_logger.handlers.clear()` するか、追加済みチェックを入れてください。

同 63 行の `raise Exception(...)` は bare `Exception` で、呼び出し側（`main.py:28`）が
「予期せぬエラー」に分類してしまいます。`RuntimeError` 等に具体化すべきです。

---

### M15. `close_application` のマジックスリープ

`app/main_window.py:89` の `time.sleep(0.1)` は UI スレッドをブロックします。
何を待っているのかコメントもなく、根拠が不明です。各 `cleanup()` が同期的に完了するなら不要です。

---

## 重大度: 低

### L1. デッドコード（本番コードから参照ゼロ / テストのみが参照）

| 対象 | 場所 |
|---|---|
| `NotificationManager.show_error_message` | `app/notification_manager.py:34` |
| `NotificationManager.show_status_message` | 同 40（かつ M7 のとおり機能しない） |
| `NotificationManager._update_status_label` | 同 58 |
| `TranscriptionHandler.wait_for_processing` | `service/transcription_handler.py:108` |
| `UIQueueProcessor.is_shutting_down` (property) | `app/ui_queue_processor.py:63` |
| `RecordingTimer.cleanup` | `service/recording_timer.py:80`（`self.cancel()` の別名のみ） |
| `AppConfig.viewer_base_url` | `utils/app_config.py:153` |
| `AppConfig.use_comma` | 同 97（書き込みのみ、読み出しなし） |
| `log_rotation.get_log_info` | `utils/log_rotation.py:130` |
| `UIComponents.update_callbacks` | `app/ui_components.py:107`（M4 参照） |

いずれも「テストがあるから生きている」状態です。テストごと削除するのが妥当です。
`../.claude/rules/coding-guidelines.md` に従い、**削除は本レビューでは実施していません**。判断をお願いします。

### L2. マジックナンバー

| 値 | 場所 | 意味 |
|---|---|---|
| `50` (ms) | `ui_queue_processor.py:20, 42` | キューポーリング間隔 |
| `10` (件) | 同 26 | 1 回のポーリングでの最大処理数 |
| `100` (ms) | `recording_lifecycle.py:160, 181` | スレッド完了チェック間隔 |
| `50` × `0.1s` | 同 269-272 | 終了待機 5 秒 |
| `5` (秒) | `recording_timer.py:41, 75` | 自動停止の事前通知 |
| `2000` (ms) | `notification_manager.py:14` | ポップアップ表示時間 |

### L3. 条件式を文として使っている

`external_service/google_stt_api.py:209`:

```python
logging.warning(error_msg) if '未指定' in str(error_msg) else logging.error(error_msg)
```

三項演算子の戻り値を捨てています。`if/else` 文か、`validate_audio_file` がログレベルを返す設計に。

### L4. 正常系を `logging.error` で記録している

`service/text_transformer.py:61` — 入力テキストが空なのはエラーではなく想定内の分岐です。`warning` が適切。

### L5. `load_replacements` の細かい点

`service/text_transformer.py:27-37`:
- `f.readlines()` はファイル全体をメモリに載せます。`for line in f:` で十分です。
- `line.split(',')` は置換後の文字列にカンマを含められません。`split(',', 1)` にすれば
  「置換前,置換後,注釈」のような行も許容できます（意図的に禁止しているなら要コメント）。
- `old.strip()` を 3 回計算しています。

### L6. 正規表現の文字範囲にコメントがない

`service/text_transformer.py:53-54` の `[぀-鿿＀-￯]` は「ひらがな〜CJK統合漢字」「全角記号」の
コードポイント範囲ですが、読んで判別できません。プロジェクト規約（「分かりにくいロジックにのみ日本語で説明」）に
まさに該当する箇所です。

### L7. Tkinter の私的 API に依存

`app/error_handler.py:11` の `tk.Misc._default_root` はアンダースコア始まりの内部属性で、
`# type: ignore` を付けて抑制しています。Tk のバージョン差で壊れる可能性があります。

### L8. `write_error_report` の 3 点

`app/error_handler.py:27-47`:
- 引数 `exc` を受け取りながら、実際には `traceback.format_exc()`（アンビエントな例外状態）を使っています。
  `traceback.format_exception(exc)` の方が引数と整合します。
- 出力先が CWD 固定の `error_log.txt`。exe 配置場所によっては書き込み権限がありません。
  ログディレクトリ配下が妥当です。
- `os.startfile()` でユーザーの意思と無関係にメモ帳を開きます。

### L9. `_config_path_cache` のモジュールグローバル

`utils/config_manager.py:7` のグローバルキャッシュは、テスト間で状態が漏れます。
`functools.lru_cache` を使えば意図が明確になり、`cache_clear()` でリセットもできます。

### L10. `../build.py`

- `print(f"Executable built successfully.")` — プレースホルダのない f-string（4 行目相当、17 行目）。
- 型ヒントなし（規約では必須）。`subprocess.run(...)` の戻り値を検査しておらず、ビルド失敗が成功と表示されます。

### L11. テストが存在しないモジュール

以下は 264 件のテストでカバーされていません:

`../app/application.py`, `../app/main_window.py`, `../app/ui_components.py`, `../app/tray_manager.py`,
`../app/error_handler.py`, `../service/keyboard_handler.py`, `../external_service/firestore_api.py`,
`../utils/config_manager.py`, `../utils/env_loader.py`, `../utils/log_rotation.py`

一方 `../tests/app/test_notification_manager.py` は 697 行あり、その相当部分が
L1 のデッドコードを対象にしています。**テストの重心が実際のリスクとずれています。**
少なくとも `config_manager` / `env_loader` / `keyboard_handler.\_to_pynput_hotkey` は
純粋関数に近く、テストしやすい割に未カバーです。

---

## 推奨する着手順

各ステップの後に `pytest tests/ -v` と `pyright app service utils` を通せば安全に進められます。

| # | 内容 | 対象 | 検証 |
|---|---|---|---|
| 1 | H5 の 1 行修正、L3・L4 の修正 | `audio_file_manager.py`, `google_stt_api.py`, `text_transformer.py` | 既存テスト緑 |
| 2 | H1: Firestore 通知を `UIQueueProcessor` 経由に | `firestore_output.py`, `application.py` | ワーカースレッドから Tk を触らないことをテストで固定 |
| 3 | M1: `constants.py` を新設し、重複 UI 文字列を集約 | 新規 + 4 ファイル | 表示文字列が変わらないことを確認 |
| 4 | M4 + M6: `update_callbacks` 削除、`setup_ui` を `__init__` に統合、assert 除去 | `ui_components.py`, `main_window.py` | 手動起動確認 |
| 5 | H2 + H3: クリップボード IPC を撤去し、ファイル文字起こしをスレッド化 | `ui_components.py`, `main_window.py`, `recording_lifecycle.py` | 音声ファイル選択の手動確認 |
| 6 | H4 + M11: `cleanup()` 順序と `AudioRecorder` の状態整理 | `recording_lifecycle.py`, `audio_recorder.py` | 録音中に終了する経路を手動確認 |
| 7 | H7 + M5: 句読点フラグを `AppConfig` に一本化、`_ui_callbacks` を属性化 | `app_config.py`, `recording_lifecycle.py`, `transcription_handler.py`, `main_window.py` | 句読点トグルの永続化を確認 |
| 8 | L1: デッドコードと対応テストの削除 | 各所 | テスト件数の減少のみ |

ステップ 1〜4 は挙動を変えないリファクタリングなので、既存の 264 件のテストがそのまま回帰検出になります。
ステップ 5 以降は挙動が変わるため、手動確認を挟んでください。
