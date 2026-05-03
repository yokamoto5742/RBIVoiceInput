# RBIVoice 新規開発プラン

RBIVoiceInput からの文字起こし結果を表示する Web ビューア。
**RBIVoiceInput とは別リポジトリ・別開発**。

## スタック

| レイヤ | 採用 |
|---|---|
| フレームワーク | React + Vite + TypeScript |
| UI | Tailwind CSS（最小限。装飾は控えめ） |
| バックエンド | Firebase（Firestore + Hosting + App Check） |
| Firestore SDK | `firebase` (Web SDK v10+) |
| デプロイ | Firebase Hosting |
| Node | 20 LTS |
| パッケージマネージャ | pnpm |

サーバー側コードなし（Firestore 直読み）。Cloud Functions も不要。

## ディレクトリ構成

```
rbivoice/
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── TranscriptView.tsx        テキストエリア
│   │   ├── PresenceBadge.tsx         録音中/切断バッジ
│   │   ├── ToolBar.tsx               コピー/クリアボタン
│   │   └── RoomGate.tsx              roomId 未指定時のエラー画面
│   ├── hooks/
│   │   ├── useSegments.ts            /rooms/{id}/segments を購読
│   │   └── usePresence.ts            /rooms/{id}/meta を購読
│   ├── lib/
│   │   ├── firebase.ts               Firebase 初期化 + App Check
│   │   └── room.ts                   URL から roomId を抽出
│   ├── constants.ts                  UI 文言（日本語）
│   └── styles.css
├── firebase.json
├── firestore.rules
├── firestore.indexes.json
├── .env.local                        VITE_FIREBASE_* 系
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## URL 設計

- ルーティング：クエリパラメータ方式 `https://rbivoice.example.com/?room={roomId}`
- `roomId` が無い場合は `RoomGate` で「URL に `?room=...` を指定してください」と表示。
- React Router は使わない（1画面のみ）。

## Firestore データモデル

### `/rooms/{roomId}/segments/{autoId}`

```ts
{
  text: string,
  createdAt: Timestamp,    // serverTimestamp()
  expiresAt: Timestamp,    // createdAt + 10min（TTL対象）
  senderId: string,
}
```

### `/rooms/{roomId}/meta` (固定docId="state")

```ts
{
  recording: boolean,
  lastPing: Timestamp,
  senderId: string,
}
```

### Firestore TTL ポリシー

- フィールド：`segments` コレクショングループの `expiresAt`
- 設定はコンソール手動。最大24時間遅延あり（仕様通り）。

### インデックス

- `segments` コレクションを `createdAt` 昇順でクエリ → 単一フィールドインデックスで自動。複合インデックス不要。

## firestore.rules

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /rooms/{roomId}/segments/{segId} {
      allow read: if request.app != null;
      allow write: if false;   // Web からは書かない
    }

    match /rooms/{roomId}/meta/{docId} {
      allow read: if request.app != null;
      allow write: if false;
    }
  }
}
```

- Sender (RBIVoiceInput) はサービスアカウント経由なのでルールをバイパスする。
- Viewer (Web) は read のみ、App Check 必須。

## App Check

- プロバイダ：reCAPTCHA Enterprise（本番）/ Debug Token（ローカル開発）
- `src/lib/firebase.ts` で `initializeAppCheck` を呼ぶ。
- Firebase Console で Firestore の App Check 強制を ON。

## コンポーネント仕様

### `TranscriptView.tsx`

- `useSegments(roomId)` で取得した配列を結合し `<textarea readOnly>` に表示。
- 各 segment は `expiresAt < now` をクライアント側でフィルタ（TTL 削除遅延対策）。
- 改行で連結（segment ごとに `\n`）。
- 自動スクロール：末尾追記時のみ最下部へスクロール。ユーザーが上にスクロール中なら追従しない。

### `PresenceBadge.tsx`

- `usePresence(roomId)` の `recording` と `lastPing` を見る。
- `recording === true && now - lastPing < 30s` → 緑バッジ「録音中」
- `recording === false` → 灰バッジ「待機中」
- `now - lastPing > 30s` → 赤バッジ「切断」

### `ToolBar.tsx`

- 「コピー」：`textarea` 全文を `navigator.clipboard.writeText` でコピー。
- 「クリア」：**ローカル表示のみクリア**（`setHiddenBefore(now)` で以降フィルタ）。Firestore は触らない。仕様通り。
- ツールチップで「Firestore のデータは PC 側からのみ削除できます」と注記。

## hooks 実装メモ

### `useSegments`

```ts
export function useSegments(roomId: string) {
  const [segments, setSegments] = useState<Segment[]>([]);
  useEffect(() => {
    const q = query(
      collection(db, 'rooms', roomId, 'segments'),
      orderBy('createdAt', 'asc'),
      limit(500)
    );
    return onSnapshot(q, (snap) => {
      setSegments(snap.docs.map(d => ({ id: d.id, ...d.data() } as Segment)));
    });
  }, [roomId]);
  return segments;
}
```

### `usePresence`

`/rooms/{roomId}/meta/state` を `onSnapshot` で購読。1 秒ごとに `setNow(Date.now())` を回して切断判定を再評価。

## 環境変数

`.env.local`：

```
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_APP_ID=
VITE_RECAPTCHA_SITE_KEY=
```

## デプロイ

```powershell
pnpm build
firebase deploy --only hosting,firestore:rules,firestore:indexes
```

`firebase.json`：

```json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [{ "source": "**", "destination": "/index.html" }]
  },
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  }
}
```

## 開発手順

1. `pnpm create vite rbivoice -- --template react-ts` でプロジェクト生成
2. `pnpm add firebase` / `pnpm add -D tailwindcss postcss autoprefixer`
3. Firebase プロジェクト（RBIVoiceInput と同一プロジェクト）で Web アプリを登録
4. `firebase.ts` に初期化コード + App Check
5. `useSegments` / `usePresence` フックを実装
6. `TranscriptView` / `PresenceBadge` / `ToolBar` を組み合わせて `App.tsx` 完成
7. ローカルで Debug Token を使い、PC 側 RBIVoiceInput から書き込みテスト
8. `firestore.rules` をデプロイ
9. App Check を強制モードに
10. Hosting にデプロイ、本番 URL で動作確認

## 動作確認チェックリスト

- [ ] `?room=tanaka-pc` で対応する PC からの文字起こしのみ表示される
- [ ] 別 `?room=...` を開くと別ストリームが見える
- [ ] PC 側で 60秒録音すると Web に逐次 final が追記される
- [ ] PC 側で「Webクリア」を押すと Firestore が空になり Web 表示も消える
- [ ] Web 側「クリア」はローカル表示のみ消える（PC 再起動で再表示される）
- [ ] PC 側を落とすと 30 秒以内に「切断」バッジ
- [ ] 10 分以上前の segment が表示されない（クライアント側フィルタ）
- [ ] App Check 無しでアクセスするとデータが読めない

## 規模見積り

- 同時 10 接続 × 10分 × 月 100 セッション ≒ 月 100,000 read 程度
- Firestore 無料枠（50K read/日 = 月 1.5M）に十分収まる
- Hosting も無料枠内
