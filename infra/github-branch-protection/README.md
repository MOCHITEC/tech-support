# GitHub ブランチ保護(任意・別モジュール)

人間承認ゲート(必須レビュー / 管理者 bypass 禁止 / stale 承認の無効化 / last-push 承認 / 必須 CI チェック)を Terraform で強制する。

本体インフラ(`infra/`)とは **別の state・別の認証**で動かす。GitHub プロバイダのみを使い、GCP には触れない。そのため本体の `terraform apply` には影響しない。

## 適用手順

```powershell
cd infra\github-branch-protection

# repo admin 権限の GitHub トークンを環境変数で渡す(コードには書かない)
$env:TF_VAR_github_token = "ghp_xxxxx"

terraform init
terraform plan
terraform apply
```

> 必須 CI チェック名(`path-guard`, `tests`)は、`.github/workflows` の job 名と一致させること。ワークフロー未作成の段階では、チェックがまだ存在せず保護が「待ち」になる場合がある。

## 注意

- あわせて repo に `.github/CODEOWNERS` を置き、`.github/` と `infra/` を人間レビュー必須にする。
- `integrations/github` プロバイダは Terraform のバージョンによってスキーマ取得に失敗することがある。その場合は `terraform init -upgrade` で別バージョンを取得するか、ブランチ保護を GitHub の Web UI(Settings → Branches)で設定する。
