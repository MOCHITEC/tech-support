variable "project_id" {
  type        = string
  description = "デプロイ先の GCP プロジェクト ID。"
}

variable "region" {
  type        = string
  description = "リソースを作成するリージョン。"
  default     = "asia-northeast1"
}

variable "name_prefix" {
  type        = string
  description = "リソース名の接頭辞。"
  default     = "tech-support"
}

variable "github_repository" {
  type        = string
  description = "owner/repo 形式。WIF の信頼条件とブランチ保護に使う。"
  default     = "MOCHITEC/tech-support"
}

variable "github_default_branch" {
  type        = string
  description = "保護・デプロイ対象のブランチ。"
  default     = "main"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL のマシンタイプ。ハッカソンは最小で十分。"
  default     = "db-f1-micro"
}

variable "db_max_connections" {
  type        = string
  description = "PostgreSQL の max_connections。並列数×pool size の総和以下に保つこと。"
  default     = "50"
}

variable "container_image" {
  type        = string
  description = "Cloud Run の初期イメージ。実イメージは CI が更新する(本リソースは image 変更を無視)。"
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "enable_github_branch_protection" {
  type        = bool
  description = "true なら GitHub のブランチ保護を Terraform で管理する(github_token が必要)。"
  default     = false
}

variable "github_token" {
  type        = string
  description = "ブランチ保護管理用の GitHub トークン(repo admin 権限)。環境変数 TF_VAR_github_token で渡す。"
  default     = ""
  sensitive   = true
}

# restricted.googleapis.com の固定 VIP レンジ(サンドボックスの egress 制限に使用)。
variable "restricted_apis_cidr" {
  type        = string
  description = "Google restricted APIs の VIP CIDR。"
  default     = "199.36.153.4/30"
}
