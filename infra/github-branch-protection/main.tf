# GitHub のブランチ保護を Terraform で明示する(人間承認ゲートの強制)。
# 本体インフラとは別モジュール。github プロバイダのみを使うため、独立して apply する。
resource "github_branch_protection" "main" {
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
    contexts = var.required_status_checks
  }
}
