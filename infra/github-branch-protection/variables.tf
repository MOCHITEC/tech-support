variable "github_repository" {
  type        = string
  description = "owner/repo 形式。"
  default     = "MOCHITEC/tech-support"
}

variable "github_default_branch" {
  type        = string
  description = "保護対象ブランチ。"
  default     = "main"
}

variable "github_token" {
  type        = string
  description = "repo admin 権限の GitHub トークン。環境変数 TF_VAR_github_token で渡す。"
  sensitive   = true
}

variable "required_status_checks" {
  type        = list(string)
  description = "マージ前に必須とする CI チェック名。"
  default     = ["path-guard", "tests"]
}
