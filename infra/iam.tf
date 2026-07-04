# ============ サービスアカウント(用途別・最小権限) ============

resource "google_service_account" "app" {
  account_id   = "${var.name_prefix}-app"
  display_name = "予約アプリ (Cloud Run)"
}

resource "google_service_account" "agents" {
  account_id   = "${var.name_prefix}-agents"
  display_name = "エージェント オーケストレータ (Cloud Run)"
}

resource "google_service_account" "sandbox" {
  account_id   = "${var.name_prefix}-sandbox"
  display_name = "テスト実行サンドボックス (Cloud Run Job)"
}

resource "google_service_account" "pubsub_push" {
  account_id   = "${var.name_prefix}-pubsub-push"
  display_name = "Pub/Sub push 用 OIDC"
}

resource "google_service_account" "deployer" {
  account_id   = "${var.name_prefix}-deployer"
  display_name = "GitHub Actions デプロイ (WIF)"
}

# ============ app SA ============

resource "google_project_iam_member" "app_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_secret_manager_secret_iam_member" "app_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app.email}"
}

resource "google_secret_manager_secret_iam_member" "app_session" {
  secret_id = google_secret_manager_secret.session_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app.email}"
}

resource "google_secret_manager_secret_iam_member" "app_webhook_secret" {
  secret_id = google_secret_manager_secret.github_webhook_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app.email}"
}

resource "google_pubsub_topic_iam_member" "app_publish" {
  topic  = google_pubsub_topic.events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.app.email}"
}

resource "google_storage_bucket_iam_member" "app_screenshots_rw" {
  bucket = google_storage_bucket.screenshots.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.app.email}"
}

# ============ agents SA ============

resource "google_project_iam_member" "agents_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.agents.email}"
}

# Vertex AI 経由で Gemini を呼ぶための権限(GCP クレジットで課金)。
resource "google_project_iam_member" "agents_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agents.email}"
}

resource "google_secret_manager_secret_iam_member" "agents_secrets" {
  for_each = {
    db     = google_secret_manager_secret.db_password.id
    github = google_secret_manager_secret.github_bot_pat.id
    gemini = google_secret_manager_secret.gemini_api_key.id
  }
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agents.email}"
}

resource "google_pubsub_topic_iam_member" "agents_publish" {
  topic  = google_pubsub_topic.events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.agents.email}"
}

resource "google_storage_bucket_iam_member" "agents_sandbox_rw" {
  bucket = google_storage_bucket.source_bundle.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.agents.email}"
}

resource "google_storage_bucket_iam_member" "agents_screenshots_ro" {
  bucket = google_storage_bucket.screenshots.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.agents.email}"
}

# サンドボックス Job を env override 付きで実行する権限(Job 単位に限定)。
# run.jobs.runWithOverrides + executions.get が必要なため developer を付与。
resource "google_cloud_run_v2_job_iam_member" "agents_run_sandbox" {
  location = var.region
  name     = google_cloud_run_v2_job.sandbox.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.agents.email}"
}

# Job 実行の LRO をポーリング(run.operations.get / run.executions.get)するため、
# プロジェクトレベルの viewer を付与。Job 単位の developer はオペレーション読み取りを
# 含まないため必要(operations はプロジェクト/ロケーション単位の別リソース)。
resource "google_project_iam_member" "agents_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.agents.email}"
}

# agents が sandbox SA を使って Job を起動できるようにする。
resource "google_service_account_iam_member" "agents_use_sandbox_sa" {
  service_account_id = google_service_account.sandbox.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.agents.email}"
}

# ============ sandbox SA(最小: 専用バケットのみ) ============

resource "google_storage_bucket_iam_member" "sandbox_bucket_rw" {
  bucket = google_storage_bucket.source_bundle.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.sandbox.email}"
}

# ============ pubsub push SA ============

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoke_agents" {
  location = var.region
  name     = google_cloud_run_v2_service.agents.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_push.email}"
}

# ============ deployer SA(GitHub Actions) ============

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  location   = var.region
  repository = google_artifact_registry_repository.containers.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# デプロイ時に各サービスの SA を「として動く」ために必要。
resource "google_service_account_iam_member" "deployer_act_as" {
  for_each = {
    app     = google_service_account.app.name
    agents  = google_service_account.agents.name
    sandbox = google_service_account.sandbox.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
