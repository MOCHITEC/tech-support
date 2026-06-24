resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "${var.name_prefix}-containers"
  format        = "DOCKER"
  description   = "アプリ・エージェント・サンドボックスのコンテナイメージ。"
  depends_on    = [google_project_service.enabled]
}
