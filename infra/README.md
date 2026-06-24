# インフラ構築手順(Terraform)

`tech-support` のクラウド基盤(Cloud Run / Cloud SQL / Pub/Sub / GCS / Secret Manager / IAM / WIF / VPC)を Terraform で構築する。

> 設計の根拠は repo ルートの `PLAN.md`(Codex レビュー反映済み Rev.5)を参照。Agent Engine は計画通り含めていない(必須と判明した場合のみ後追加)。

---

## 1. 前提ツールのインストール(Windows)

### Terraform CLI
```powershell
winget install HashiCorp.Terraform
terraform version    # >= 1.6
```

### Google Cloud SDK(gcloud)
```powershell
winget install Google.CloudSDK
gcloud version
```
インストール後、新しい PowerShell を開いて `gcloud` が通ることを確認する。

---

## 2. GCP プロジェクトの準備

```powershell
# ログイン(2種類: CLI 操作用と、Terraform が使う Application Default Credentials)
gcloud auth login
gcloud auth application-default login

# プロジェクト作成(既存を使う場合はスキップ)
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID

# 課金アカウントの紐付け(課金 ID は `gcloud billing accounts list` で確認)
gcloud billing projects link YOUR_PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX
```

> API の有効化は Terraform(`apis.tf`)が行うので手動操作は不要。

---

## 3. 変数の設定

```powershell
cd infra
Copy-Item terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集し、project_id などを設定する
```

`terraform.tfvars` と `*.tfstate` は秘密情報を含むため git 管理しない(`infra/.gitignore` で除外済み)。

---

## 4. 適用

```powershell
terraform init
terraform plan      # 作成内容を確認
terraform apply     # yes で実行(初回は API 有効化〜DB 作成で 10〜20 分程度)
```

---

## 5. 適用後の作業

### 5-1. 外部シークレットの値を投入
`github_bot_pat` と `gemini_api_key` はコンテナのみ作成される。値を投入する:

```powershell
# GitHub ボットの Fine-grained PAT(このリポジトリ限定 / contents:write, pull_requests:write, issues:write / workflow スコープなし)
"ghp_xxxxx" | gcloud secrets versions add tech-support-github-bot-pat --data-file=-

# Gemini API キー
"AIza_xxxxx" | gcloud secrets versions add tech-support-gemini-api-key --data-file=-
```

### 5-2. 初期イメージのビルドと push(任意)
Cloud Run は初期 placeholder イメージで作成される。実イメージは GitHub Actions(デプロイ workflow)が push・更新する。手動で確認したい場合:

```powershell
$repo = terraform output -raw artifact_registry
gcloud auth configure-docker "$($repo.Split('/')[0])"
docker build -t "$repo/app:bootstrap" ..
docker push "$repo/app:bootstrap"
```

### 5-3. GitHub Actions(WIF)の設定
デプロイ workflow が長期キーなしでデプロイできるよう、以下の出力値を使う:

```powershell
terraform output workload_identity_provider   # → auth アクションの workload_identity_provider
terraform output deployer_service_account     # → auth アクションの service_account
```

`.github/workflows/deploy.yml` の `google-github-actions/auth` に上記2値を設定する(workflow は別途作成)。

### 5-4. ブランチ保護(任意・推奨)
人間承認ゲートは**別モジュール** `infra/github-branch-protection/` で適用する(GitHub プロバイダのみを使い、本体とは独立)。手順はそのディレクトリの `README.md` を参照。

> ブランチ保護を本体から分離している理由: `integrations/github` プロバイダは Terraform のバージョンによってスキーマ取得に失敗することがあり、本体の `plan`/`apply` を巻き込まないようにするため。

---

## 6. 後片付け

```powershell
terraform destroy
```
バケットは `force_destroy=true`、Cloud SQL は `deletion_protection=false` のため破棄可能。

---

## リソース概要

| ファイル | 内容 |
|---|---|
| `apis.tf` | 必要 API の有効化 |
| `network.tf` | VPC・サブネット(PGA)・コネクタ・**サンドボックスの egress を restricted APIs のみに制限** |
| `artifact_registry.tf` | コンテナイメージのリポジトリ |
| `cloudsql.tf` | PostgreSQL(max_connections 上限つき) |
| `storage.tf` | 非公開バケット(スクショ / サンドボックス用) |
| `pubsub.tf` | イベントトピック・DLQ・OIDC push サブスクリプション |
| `secrets.tf` | Secret Manager(自動生成 + 外部投入) |
| `iam.tf` | 用途別 SA と最小権限バインディング |
| `wif.tf` | GitHub Actions 用 Workload Identity 連携(リポジトリ・ブランチ限定) |
| `cloudrun.tf` | app / agents サービス + サンドボックス Job |
| `github-branch-protection/` | ブランチ保護(任意・別モジュール) |

## 注意

- `terraform validate` は google/random プロバイダで通過確認済み。`integrations/github` プロバイダはお手元の環境で初めてスキーマ取得される(本サンドボックスでは未検証)。
- `apply` は課金が発生する。ハッカソン後は `terraform destroy` を実行すること。
- Cloud Run の実イメージ更新は CI に委ねるため、本構成は image 変更を無視(`ignore_changes`)する。
