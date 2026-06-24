# GitHub のブランチ保護を Terraform で明示する(人間承認ゲートの強制)。
# enable_github_branch_protection=true かつ github_token 設定時のみ作成。
resource "github_branch_protection" "main" {
  count = var.enable_github_branch_protection ? 1 : 0

  repository_id  = split("/", var.github_repository)[1]
  pattern        = var.github_default_branch
  enforce_admins = true # 管理者も bypass 不可

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews           = true # 新規 push で過去の承認を無効化
    require_code_owner_reviews      = true
    require_last_push_approval      = true # 最新 push の承認を必須
  }

  required_status_checks {
    strict   = true
    contexts = ["path-guard", "tests"]
  }
}
