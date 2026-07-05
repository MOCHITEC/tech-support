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

variable "github_app_id" {
  type        = string
  description = "GitHub App の App ID(push/PR/Issue 用の installation token 発行に使う)。"
  default     = "4218791"
}

variable "github_app_installation_id" {
  type        = string
  description = "GitHub App のインストール ID(MOCHITEC/tech-support へのインストール)。"
  default     = "144466688"
}

variable "pr_reviewers" {
  type        = string
  description = "自動生成 PR に付けるレビュアー(GitHub ログインのカンマ区切り)。"
  default     = "EndoRai88"
}

variable "github_default_branch" {
  type        = string
  description = "保護・デプロイ対象のブランチ。"
  default     = "main"
}

variable "pr_base_branch" {
  type        = string
  description = "エージェントが自動生成する PR の作成先ブランチ(main を汚さないためデモでは demo)。"
  default     = "demo"
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

variable "allow_public_app" {
  type        = bool
  description = "予約アプリを allUsers で一般公開するか。組織ポリシーで公開禁止の場合は false。"
  default     = false
}

# restricted.googleapis.com の固定 VIP レンジ(サンドボックスの egress 制限に使用)。
variable "restricted_apis_cidr" {
  type        = string
  description = "Google restricted APIs の VIP CIDR。"
  default     = "199.36.153.4/30"
}
