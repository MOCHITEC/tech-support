resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  name             = "${var.name_prefix}-pg"
  database_version = "POSTGRES_15"
  region           = var.region

  # ハッカソンの後片付けを容易にするため保護を無効化する。
  deletion_protection = false

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"

    ip_configuration {
      # 公衆ネットワークからの直接接続は許可せず、Cloud SQL コネクタ経由のみ。
      ipv4_enabled = true
      authorized_networks {
        name  = "none"
        value = "127.0.0.1/32"
      }
    }

    database_flags {
      name  = "max_connections"
      value = var.db_max_connections
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_sql_database" "app" {
  name     = "techsupport"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app" {
  name     = "appuser"
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}
