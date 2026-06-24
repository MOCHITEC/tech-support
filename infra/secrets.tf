# --- 自動生成して Terraform が版を作るシークレット ---

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.name_prefix}-db-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

resource "random_password" "session" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret" "session_secret" {
  secret_id = "${var.name_prefix}-session-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_version" "session_secret" {
  secret      = google_secret_manager_secret.session_secret.id
  secret_data = random_password.session.result
}

# --- 外部から値を投入するシークレット(コンテナのみ作成) ---
# 値は apply 後に手動投入する:
#   gcloud secrets versions add tech-support-github-bot-pat --data-file=-
#   gcloud secrets versions add tech-support-gemini-api-key --data-file=-

resource "google_secret_manager_secret" "github_bot_pat" {
  secret_id = "${var.name_prefix}-github-bot-pat"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "${var.name_prefix}-gemini-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}
