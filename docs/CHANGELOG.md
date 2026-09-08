# 変更履歴

このプロジェクトのすべての重要な変更は、このファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に基づいており、
バージョン番号は [Semantic Versioning](https://semver.org/lang/ja/) に従っています。

## [Unreleased]

## [1.0.1] - 2026-09-08

### 追加
- UI文字列定数（`constants.py`）をユーティリティレイヤーに統一

### 変更
- FirestoreOutput のエラー通知を UIQueueProcessor 経由で処理するように変更
- TextTransformer の空テキストログレベルを warning に変更
- RecordingLifecycle の UI コールバックとステータス表示を改善
- ウィンドウのデフォルト高さを 450px から 350px に変更

### 修正
- UIQueueProcessor の `is_shutting_down` プロパティを削除
- AudioRecorder の `is_recording` フラグの動作を修正
- AudioFileManager で `pyaudio.get_sample_size()` を正しく使用
- AppConfig から不要な `use_comma` プロパティを削除
- Google STT API のエラーログレベルを修正
- TranscriptionHandler の句読点処理設定を config から取得
- MainWindow の UI 初期化とコールバック設定を修正
- UIComponents の初期化と UI 要素の更新処理を修正
- RecordingLifecycle のクリーンアップ処理を改善
- LogRotation から不要な関数を削除

### 削除
- 句読点切替機能（`toggle_punctuation` キー、句読点ボタン、`use_punctuation` / `use_comma` 設定）を削除
- 音声ファイル再読込キー機能（`reload_audio` キー）を削除
- 閉じるボタンのショートカットキー機能（`exit_app` キー）を削除し、ボタン操作のみに変更
- RecordingTimer の `cleanup()` メソッドを削除

## [1.0.0] - 2026-05-03
- RBIVoiceInput の初版リリース
