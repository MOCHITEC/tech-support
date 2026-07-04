# tech-support — ユーザの声が CI/CD を動かすフィードバック駆動パイプライン

> ユーザのバグ報告がそのまま「失敗するテスト」になり、AI エージェントが再現・修正して
> PR を作成、**人間の承認**を経てデプロイ・リリースされる。ユーザから見える CI/CD。

**DevOps × AI Agent Hackathon 2026**(Findy 主催 / Google Cloud 協賛)応募作品。

- 公開アプリ(デモ): https://tech-support-app-3z3aqgv5sq-an.a.run.app

---

## コンセプト

従来「バグ報告 → 開発者が対応」だったループを、**報告 → AI エージェントが再現テスト生成 →
修正 → PR → 人間承認 → デプロイ → 報告者へリリース通知** という一連の CI/CD として
自動化する。ユーザは自分の声がリリースに反映される過程を、ステータスページで追える。

判定・修正の**根拠**は、報告時点で固定した `docs/仕様書.md`(ある commit SHA 時点)。
これにより「なぜバグ/要望と判断したか」を説明可能・再現可能にする。

---

## パイプラインの流れ

```
ユーザ報告(フォーム+スクショ)
   │  Pub/Sub 発行
   ▼
オーケストレータ(agents / Cloud Run, 非公開)  ← Pub/Sub push (OIDC)
   │  inbox に冪等記録(UNIQUE)+ lease で二重処理防止
   ▼
トリアージ(Gemini)  ── feature → 要件定義 Issue 起票 → 終了
   │                 ── 重複/情報不足 → 状態遷移して終了
   │  bug
   ▼
再現テスト生成 → サンドボックス Job(秘密ゼロ・外向き遮断)で実行
   │  再現できない → 追加情報待ち
   ▼
修正の自己ループ(最大5回, サンドボックスで検証)
   │  グリーン
   ▼
PR 作成(ボット PAT) → 人間レビュー/承認 → マージ
   │  GitHub webhook(HMAC 検証)
   ▼
デプロイ → 対象チケットを「リリース済み」へ同期
```

- レビューで `@agent fix` とコメント(write 権限者・ボット PR・コマンド形式を全検証)すると再修正。

---

## アーキテクチャ

| コンポーネント | 実体 | 役割 |
|---|---|---|
| **app** | Cloud Run(公開) | 会議室予約アプリ・フィードバックフォーム・ステータスページ・GitHub webhook 受信 |
| **agents** | Cloud Run(非公開) | オーケストレータ。Pub/Sub push を受け、triage→再現→修正→PR を実行 |
| **sandbox** | Cloud Run Job | LLM 生成テストを隔離実行(秘密情報ゼロ・egress 遮断・専用 SA) |
| **migrate** | Cloud Run Job | デプロイ前に `alembic upgrade head` + デモデータ投入 |
| データ/連携 | Cloud SQL(PostgreSQL) / Pub/Sub + DLQ / GCS / Secret Manager / Artifact Registry | 永続化・非同期・スクショ保存・秘密・イメージ |
| 認証/隔離 | Workload Identity 連携(WIF) / VPC(restricted egress) | 長期キーなしデプロイ・サンドボックスの通信制限 |

すべて **Terraform**(`infra/`)でコード化。CI/CD は **GitHub Actions**。

---

## 題材アプリと仕込みバグ

会議室予約システム(FastAPI + Jinja2 + SQLAlchemy)。デモ用に3つのバグを仕込んである:

1. **二重予約ができる**(メインデモ)
2. **2時間以上の割引が適用されない**
3. **過去日の予約もキャンセルできる**

正式仕様は [`docs/仕様書.md`](docs/仕様書.md)、状態遷移は [`docs/状態機械.md`](docs/状態機械.md) を参照。

---

## セキュリティ設計(要点)

- **入力は全て非信頼**。LLM 出力は Pydantic スキーマで検証し、ファイル操作・git・GitHub API は
  **許可リスト化された決定論コードのみ**が実行(LLM がコマンドを直接実行しない)。
- **サンドボックス隔離**: 生成テストは秘密情報ゼロ・外向き通信遮断の Cloud Run Job で実行。
- **アプリ層**: 署名付きセッション + CSRF + Origin 検証 + レート制限 + 所有者検証(IDOR 対策)。
- **CI 分離**: PR テスト workflow は `contents:read`・secrets ゼロ。**変更パスガード**を先行 job にし、
  範囲外(app/・tests/ 以外、app/agents/)の生成コードはテスト前に拒否。
- **ブランチ保護 + CODEOWNERS**: `.github/` `infra/` 等は人間承認必須。
- **WIF**: デプロイは長期 SA キーなし、信頼条件をリポジトリ・main ブランチに限定。
- **webhook**: 公開エンドポイントは HMAC 署名検証のみで受理。

---

## 技術スタック

FastAPI / SQLAlchemy / Alembic / Pydantic / Jinja2 / Pillow ・ Gemini API(`google-genai`)・
Cloud Run / Cloud Run Jobs / Pub/Sub / Cloud SQL / GCS / Secret Manager ・ Terraform ・
GitHub Actions(WIF)・ pytest(単体=SQLite、統合=PostgreSQL)。

---

## ディレクトリ構成

```
app/            予約アプリ(FastAPI)
  agents/       エージェント(triage/再現修正/PR/レビュー/sandbox/webhook 等)
  migrations/   Alembic
docs/           仕様書・状態機械・マニュアル・webhook 設定手順
infra/          Terraform(本体 + github-branch-protection モジュール)
tests/          TDD テスト一式
.github/        deploy.yml / test.yml / CODEOWNERS
PLAN.md         確定計画(Codex レビュー反映済み Rev.5)
```

---

## ローカル開発

Python は `py`(Windows)、仮想環境は `.venv`。

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# テスト(単体は SQLite で数秒)
.venv\Scripts\python.exe -m pytest -q

# アプリ起動(未設定時はローカル SQLite)
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

DB 接続は環境変数で切替: `DATABASE_URL` 明示 > Cloud SQL(`INSTANCE_CONNECTION_NAME` 等)> ローカル SQLite。

---

## デプロイ / インフラ

手順の詳細は [`infra/README.md`](infra/README.md)、webhook 設定は [`docs/webhook-setup.md`](docs/webhook-setup.md)。

```powershell
cd infra
terraform init
terraform apply            # GCP 基盤を構築
```

初回のクラウド起動順序(共有イメージと Terraform の依存を解くため):

1. `terraform apply -target=google_cloud_run_v2_job.migrate`(Job 作成)
2. GitHub Actions の **deploy** workflow を実行(実イメージ build → migrate 実行 → app/agents デプロイ)
3. `terraform apply`(agents を orchestrator コマンドへ切替 ほか)

---

## 応募要件との対応

- **実行環境**: Cloud Run(app / agents / Jobs)
- **AI**: Gemini API(`google-genai`)
- **DevOps サイクル**: 計画(PLAN.md/仕様書)→ 開発(TDD)→ デプロイ(WIF + Actions)→ 運用
  (Pub/Sub 非同期・DLQ・状態機械・ステータスページ・リリース通知)を通しで体現。

---

## ドキュメント

- [PLAN.md](PLAN.md) — 確定計画(Rev.5)
- [docs/仕様書.md](docs/仕様書.md) — 予約アプリの正式仕様(判定の ground truth)
- [docs/状態機械.md](docs/状態機械.md) — チケット状態遷移
- [docs/MANUAL.md](docs/MANUAL.md) — 操作マニュアル
- [docs/webhook-setup.md](docs/webhook-setup.md) — GitHub webhook 設定手順
- [infra/README.md](infra/README.md) — インフラ構築手順
