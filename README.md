# RBIVoiceInput

**日本語の専門用語に強いWindows 用ショートカット型音声入力ツール**

指定したキー（デフォルト: Ctrl+Alt+V）で録音開始/終了、文字起こし結果を Firestore にリアルタイム出力して RBIVoice で表示。1 日 200 回以上の短文作成が可能な設計です。

---

## 目次

- [RBIVoiceInput 開発の経緯](#RBIVoiceInput-開発の経緯)
- [想定ユーザーと使用シーン](#想定ユーザーと使用シーン)
- [特徴](#特徴)
- [専門用語登録](#専門用語登録)
- [置換ルールのサンプル](#置換ルールのサンプル)
- [文字起こし結果の出力](#文字起こし結果の出力)
- [クイックスタート](#クイックスタート)
- [使い方](#使い方)
- [設計のポイント](#設計のポイント)
- [設定](#設定)
- [開発者向け情報](#開発者向け情報)
- [システム要件](#システム要件)
- [トラブルシューティング](#トラブルシューティング)
- [ライセンス](#ライセンス)
- [更新履歴](#更新履歴)
- [免責事項](#免責事項)

---

## RBIVoiceInput 開発の経緯

既存の音声入力アプリには、以下のような不都合がありました。

- ❌ **Windows 標準の音声入力は日本語の認識精度が弱い**
- ❌ **複数デバイスでのリアルタイム同期が困難**
- ❌ **ネット瞬断時に音声が消失して再度発声が必要**

RBIVoiceInput はこれらを次の組み合わせで解決します。

- **Google Cloud Speech-to-Text API** による日本語認識精度
- **Firestore** による複数デバイスとのリアルタイム同期
- **ローカル音声ファイル保存** による通信瞬断への耐性

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 想定ユーザーと使用シーン

パソコンで事務作業を行う方が、以下の用途で使うことを想定しています。

- 業務メール文章の作成
- ファイル名、チャット欄などへの直接入力
- 生成 AI へのプロンプト入力
- 議事録の作成

**想定ワークフロー:** 1 日 200 回 × 1 回 60 秒以下の **短文作成** 型。長時間音声の文字起こしではなく、思いついたときにショートカットキーで素早く短文を入力する用途に最適です。

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 特徴

1. **ショートカットで録音** — Ctrl+Alt+V で録音開始/終止（録音中は画面右下のツールバーにマイクマークが表示）
2. **Firestore へリアルタイム出力** — 文字起こし結果を Firestore に書き込み、RBIVoice で確認・管理
3. **複数デバイス対応** — Firestore を通じて複数デバイスからのリアルタイム同期に対応
4. **システムトレイ機能** — ウィンドウ最小化時にシステムトレイに収納できます
5. **ネット瞬断に強い** — 音声はローカルに保存されるため通信失敗時も再送可能
6. **専門用語登録機能** — 専門用語を登録して認識精度を向上
7. **置換ルールによる後処理置換** — `data/replacements.txt` に登録して誤認識を修正

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 専門用語登録機能

`data/technical_terms.txt` に専門用語を登録すると、Google Cloud Speech-to-Text API にフレーズヒントとして送信され、認識精度が向上します。

### 登録方法

`data/technical_terms.txt` に 1 行 1 フレーズで登録します。

```
$OOV_CLASS_DIGIT_SEQUENCE
$OPERAND
加齢黄斑変性
```

- **クラストークン** (`$OOV_CLASS_*`) — Google STT API の特殊トークン。数字列や演算子など、クラスベースの認識ヒント
- **テキストフレーズ** — 医療用語や業界用語など、固有の専門用語

### 実装動作

アプリケーション起動時に `data/technical_terms.txt` を読み込み、STT API へ `speech_recognition_hints` として設定されます。これにより以下のような効果が期待できます。

- 医療系の専門用語（「加齢黄斑変性」など）の誤認識を削減
- 部署名や業務用語の正確な認識

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 置換ルールのサンプル

`data/replacements.txt` に CSV 形式で登録します。実際の運用例を抜粋します。

```csv
# 医療系の同音異義語を補正
小児体,硝子体

# 不要な疑問符を句点に
?,。
```

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 文字起こし結果の出力

文字起こし結果を Firestore に書き込み、RBIVoice で確認・管理できます。複数デバイスからのリアルタイム同期に対応しています。

**動作フロー：**
1. 録音開始時に録音状態を Firestore に記録（presence）
2. 文字起こし完了後、テキストを Firestore の segments コレクションに追記
3. RBIVoice が Firestore からリアルタイムに新規テキストを取得・表示
4. TTL（デフォルト: 10 分）経過後、自動削除

**必要な準備：**
- Google Cloud の Firestore データベース
- サービスアカウント認証情報（JSON）
- Firestore のプロジェクト ID と room ID の設定

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## クイックスタート

### 1. リポジトリをクローン

```bash
git clone https://github.com/your-repo/RBIVoiceInput.git
cd RBIVoiceInput
```

### 2. 仮想環境の作成と依存パッケージのインストール

事前に [uv](https://docs.astral.sh/uv/getting-started/installation/) のインストールが必要です。

```bash
# 仮想環境の作成とパッケージのインストールを一度に行う
uv sync
```

仮想環境を有効化する：

```bash
# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Mac / Linux
source .venv/bin/activate
```

### 3. Firestore と Google Cloud API キーを設定

`.env` ファイルにサービスアカウント認証情報と Firestore 設定を記述します。

#### 3-1. サービスアカウントキーを取得

Google Cloud Console からサービスアカウントキーの JSON ファイルをダウンロードします。

#### 3-2. .env ファイルを作成

```
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_LOCATION=asia-northeast1
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-gcp-project-id","private_key_id":...}
```

JSON が複数行の場合は 1 行に変換してください（改行がない状態）。

#### 3-3. config.ini を更新

`utils/config.ini` の `[FIRESTORE]` セクションを設定します：

```ini
[FIRESTORE]
project_id = your-gcp-project-id
room_id = unique-room-identifier
collection = rooms
ttl_minutes = 10
viewer_base_url = https://your-viewer-app.web.app
presence_ping_interval = 10
```

- `project_id`: Firestore が有効な GCP プロジェクト ID
- `room_id`: このアプリ インスタンスの一意の ID（RBIVoice で識別用）
- `collection`: Firestore のルートコレクション名（デフォルト: `rooms`）
- `ttl_minutes`: Firestore に保存する segments のデフォルト TTL（分）
- `viewer_base_url`: RBIVoice のベース URL（オプション）

### 4. 起動

```bash
python main.py
```

起動後、Ctrl+Alt+V を押して録音 → 話す → Ctrl+Alt+V で停止すると、テキストが Firestore に書き込まれ、RBIVoice にリアルタイム表示されます。

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 使い方

### キーボードショートカット

| キー         | 機能           |
|-------------|---------------|
| Ctrl+Alt+V  | 録音開始 / 停止 |

### 基本フロー

1. Ctrl+Alt+V を押して録音開始
2. マイクに向かって話す（デフォルトは最大 60 秒で自動停止）
3. Ctrl+Alt+V で停止、または 60 秒自動停止
4. テキストが自動的に Firestore に書き込まれ、RBIVoice にリアルタイム表示

音声データはローカルに保存されているため、ネット切断などで変換に失敗した場合でも再送信が可能です。

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 設計のポイント

### レイヤー構成

- **`app/`** — Tkinter UI レイヤー。ウィンドウ、トレイ、通知、ホットキー設定。全 UI 更新は `UIQueueProcessor` 経由
- **`service/`** — ビジネスロジック。`RecordingLifecycle` が `AudioRecorder` → `TranscriptionHandler` → `TextTransformer` → `FirestoreOutput` のパイプラインを統合
- **`external_service/`** — Google Cloud Speech-to-Text API、Firestore API の薄いラッパー
- **`utils/`** — 設定 (`AppConfig`)、ロギング、クラッシュログ、環境変数読み込み

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 設定

### 主要な設定 (utils/config.ini)

| セクション | 用途 |
|-----------|------|
| `[GOOGLE_STT]` | モデル (`chirp_3`)、言語 (`ja-JP`)、専門用語フレーズセット |
| `[FIRESTORE]` | プロジェクト ID、room ID、Firestore コレクション名、TTL |
| `[KEYS]` | ショートカット割り当て（デフォルト: `ctrl+alt+v`） |
| `[RECORDING]` | 自動停止タイマー（デフォルト 60 秒） |
| `[PATHS]` | 置換ルールファイル、一時ファイル保存先 |
| `[AUDIO]` | サンプルレート、チャネル数、チャンク サイズ |
| `[LOGGING]` | ログレベル、ログディレクトリ、保持日数 |

その他のセクションは `config.ini` 内を参照してください。

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## 開発者向け情報

### テスト

```bash
python -m pytest tests/ -v --tb=short
python -m pytest tests/ -v --tb=short --cov=app --cov-report=html
```

### 型チェック

```bash
pyright app service utils
```

### 実行ファイルのビルド

```bash
python build.py
```

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## システム要件

- Windows 11
- Python 3.12 以上
- マイク入力デバイス
- Google Cloud プロジェクト（Firestore と Speech-to-Text API が有効）

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## トラブルシューティング

### Firestore へ接続できない、またはテキストが出力されない

- `.env` に `GOOGLE_CREDENTIALS_JSON` と `GOOGLE_PROJECT_ID` が正しく設定されているか確認
- `config.ini` の `[FIRESTORE]` セクションで `project_id` と `room_id` が設定されているか確認
- Google Cloud ダッシュボードで Firestore が有効になっているか確認
- サービスアカウントに Firestore への読み書き権限があるか確認（IAM ロール: `Cloud Datastore User`）

### 音声が録音されない

1. Windows の設定でマイクが有効か確認
2. 他のアプリがマイクを占有していないか確認
3. PyAudio の動作確認: `python -c "import pyaudio; print('OK')"`

### 文字起こしが開始されない

- ネットワーク接続を確認
- Google Cloud Speech-to-Text API が有効になっているか確認
- サービスアカウント認証情報に Speech-to-Text API へのアクセス権があるか確認

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>

---

## ライセンス

ライセンス情報は [LICENSE](docs/LICENSE) を参照してください。

## 更新履歴

更新履歴は [CHANGELOG.md](docs/CHANGELOG.md) を参照してください。

## 免責事項

Google Cloud Speech-to-Text と Firestore をご利用の際は、個人を特定できる医療情報や機密情報は入力しないでください。

本ツールは、Google Cloud サービスを通じた音声データおよび文字起こしデータの取り扱いに起因するいかなる損害についても、責任を負いかねます。

詳細は、Google Cloud の公式サイトにてプライバシーポリシーおよび利用規約をご確認ください。Firestore のデータ削除ポリシーについても事前に確認してください。

<div align="right"><a href="#目次">▲ 目次へ戻る</a></div>
"# RBIVoiceInput" 
