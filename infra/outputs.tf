output "app_url" {
  description = "予約アプリの URL。"
  value       = google_cloud_run_v2_service.app.uri
}

output "agents_url" {
  description = "エージェントサービスの URL。"
  value       = google_cloud_run_v2_service.agents.uri
}

output "artifact_registry" {
  description = "コンテナイメージの push 先(REGION-docker.pkg.dev/PROJECT/REPO)。"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "screenshots_bucket" {
  value = google_storage_bucket.screenshots.name
}

output "source_bundle_bucket" {
  value = google_storage_bucket.source_bundle.name
}

output "instance_connection_name" {
  value = google_sql_database_instance.main.connection_name
}

output "events_topic" {
  value = google_pubsub_topic.events.name
}

# ---- GitHub Actions の WIF 設定に使う ----
output "deployer_service_account" {
  description = "GitHub Actions が引き受けるデプロイ SA。"
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "google-github-actions/auth の workload_identity_provider に設定する値。"
  value       = google_iam_workload_identity_pool_provider.github.name
}

# ---- 手動投入が必要なシークレット ----
output "secrets_to_populate" {
  description = "apply 後に値を投入する Secret Manager のシークレット名。"
  value = [
    google_secret_manager_secret.github_bot_pat.secret_id,
    google_secret_manager_secret.gemini_api_key.secret_id,
  ]
}
