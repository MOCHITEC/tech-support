# スクリーンショット用の非公開バケット(所有者検証済み API 経由でのみ取得)。
resource "google_storage_bucket" "screenshots" {
  name                        = "${var.project_id}-${var.name_prefix}-screenshots"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7 # デモ後の保持を短くする。
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled]
}

# サンドボックス Job 用のソース bundle・結果受け渡しバケット(Job 専用)。
resource "google_storage_bucket" "source_bundle" {
  name                        = "${var.project_id}-${var.name_prefix}-sandbox"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled]
}
