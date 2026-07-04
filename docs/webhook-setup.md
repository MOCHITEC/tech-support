# GitHub Webhook 設定手順

PR のマージ/クローズによるチケット状態同期と、レビューでの `@agent fix` 起動のために
GitHub Webhook を設定する。公開アプリの `/webhook/github` エンドポイントが受信し、
HMAC 署名で認証する。

前提: 予約アプリ(app サービス)が一般公開済みで GitHub から到達できること。

---

## ステップ1 — Webhook シークレットの値を取得する

`gcloud` CLI のログインが切れている場合は、まずインタラクティブな端末でログインする:

```
gcloud auth login
```

シークレット(GitHub 側に設定する値)を読み取る:

```
gcloud secrets versions access latest --secret=tech-support-github-webhook-secret --project=ace-ripsaw-498301-f5
```

出力された値をそのままコピーする(48 文字の文字列。**末尾の改行や空白を含めない**)。

---

## ステップ2 — リポジトリの Webhook 設定を開く

1. **https://github.com/MOCHITEC/tech-support** にアクセスする
2. リポジトリ右上の **Settings(設定)** → 左サイドバーの **Webhooks** → **Add webhook(Webhook を追加)** をクリック
   - リポジトリの **admin(管理者)権限** が必要。`EndoRai88` に admin 権限が無い場合は、MOCHITEC リポジトリを所有するアカウントで操作する。
3. GitHub からパスワード / 2FA(二要素認証)の確認を求められたら、認証を完了する

---

## ステップ3 — フォームに入力する

| 項目 | 値 |
|---|---|
| **Payload URL** | `https://tech-support-app-3z3aqgv5sq-an.a.run.app/webhook/github` |
| **Content type** | `application/json` ← フォーム形式ではなく必ず JSON |
| **Secret(シークレット)** | *(ステップ1で取得した値を貼り付け)* |
| **SSL verification(SSL 検証)** | **有効のまま**(既定。URL は HTTPS) |

---

## ステップ4 — 送信するイベントを選ぶ

1. 「Which events would you like to trigger this webhook?(どのイベントで起動するか)」で **「Let me select individual events.(個別のイベントを選択する)」** を選ぶ
2. 既定の **「Pushes」のチェックを外す**
3. 次の2つだけに **チェックを入れる**:
   - ☑ **Pull requests** → マージで `RELEASED`、未マージクローズで `PR_REJECTED` に遷移
   - ☑ **Issue comments** → `@agent fix` を起動
4. **「Active(有効)」** にチェックが入っていることを確認 → **Add webhook(Webhook を追加)**

---

## ステップ5 — 動作確認

1. 保存すると GitHub が `ping` を送信する。Webhook を開き **Recent Deliveries(最近の配信)** を確認する。
2. 配信をクリックすると **Response 204** が表示されるはず(エンドポイントは対象外イベントを ack して無視する)。204 = 署名検証成功 + 到達成功。
   - **401** → シークレットがステップ1の値と一致していない(空白を含めず貼り直す)。
   - **タイムアウト / 5xx** → URL が誤っているか app が停止している(ステップ3の URL を再確認)。
3. 任意の配信の **「Redeliver(再送)」** で、実際の GitHub 操作なしに再テストできる。

---

## 各設定の役割

- **Content type = JSON + Secret**: app は何かを行う前に `X-Hub-Signature-256`(HMAC)を検証する。これがこの公開エンドポイント唯一の認証。
- **Pull requests**: マージ時、対象チケット(ブランチ `agent/ticket-{id}-fix`)が「リリース済み」へ。未マージクローズ時は「PR却下」へ。
- **Issue comments**: レビュアーがボット PR に `@agent fix`(write 権限が必要)とコメントすると再修正を起動。app がコメント・投稿者権限・コマンド形式を検証してから実行する。
