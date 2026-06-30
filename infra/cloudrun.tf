# 実イメージは CI が更新するため image 変更は無視する(初期は placeholder)。

# ============ 予約アプリ ============
resource "google_cloud_run_v2_service" "app" {
  name                = "${var.name_prefix}-app"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # ハッカソンの後片付けを容易にする

  template {
    service_account = google_service_account.app.email

    containers {
      image = var.container_image

      env {
        name  = "DB_USER"
        value = google_sql_user.app.name
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.app.name
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.main.connection_name
      }
      env {
        name  = "SCREENSHOT_BUCKET"
        value = google_storage_bucket.screenshots.name
      }
      env {
        name  = "EVENTS_TOPIC"
        value = google_pubsub_topic.events.name
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.session_secret.secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    scaling {
      max_instance_count = 4
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }

  depends_on = [google_project_service.enabled]
}

# 予約アプリの一般公開(allUsers)。組織ポリシーで公開が禁止されている場合は
# allow_public_app=false のままにし、公開は別途ポリシー対応で行う。
resource "google_cloud_run_v2_service_iam_member" "app_public" {
  count    = var.allow_public_app ? 1 : 0
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ============ エージェント オーケストレータ ============
resource "google_cloud_run_v2_service" "agents" {
  name                = "${var.name_prefix}-agents"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # Pub/Sub push は OIDC+run.invoker で限定
  deletion_protection = false

  template {
    service_account = google_service_account.agents.email

    containers {
      image = var.container_image

      # 共有イメージを agents として起動するためオーケストレータ ASGI を指定。
      command = ["sh", "-c"]
      args    = ["exec uvicorn app.agents.server:orchestrator --host 0.0.0.0 --port $PORT"]

      env {
        name  = "DB_USER"
        value = google_sql_user.app.name
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.app.name
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.main.connection_name
      }
      env {
        name  = "SOURCE_BUNDLE_BUCKET"
        value = google_storage_bucket.source_bundle.name
      }
      env {
        name  = "SANDBOX_JOB"
        value = "${var.name_prefix}-sandbox"
      }
      env {
        name  = "EVENTS_TOPIC"
        value = google_pubsub_topic.events.name
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_bot_pat.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    scaling {
      max_instance_count = 2
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }

  depends_on = [google_project_service.enabled]
}

# ============ テスト実行サンドボックス(Cloud Run Job) ============
resource "google_cloud_run_v2_job" "sandbox" {
  name     = "${var.name_prefix}-sandbox"
  location = var.region

  template {
    template {
      service_account = google_service_account.sandbox.email
      max_retries     = 1
      timeout         = "600s"

      containers {
        image   = var.container_image
        command = ["python", "-m", "app.agents.sandbox_main"]
        env {
          name  = "SOURCE_BUNDLE_BUCKET"
          value = google_storage_bucket.source_bundle.name
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }

      # 全 egress を VPC 経由にし、ファイアウォールで restricted APIs 以外を遮断。
      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "ALL_TRAFFIC"
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.enabled]
}

# ============ マイグレーション(Cloud Run Job) ============
# デプロイのトラフィック切替前に CI が一度だけ実行する(PLAN §5)。agents SA を
# 再利用(cloudsql.client + db_password の secretAccessor を既に保有)。
resource "google_cloud_run_v2_job" "migrate" {
  name                = "${var.name_prefix}-migrate"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.agents.email
      max_retries     = 0
      timeout         = "600s"

      containers {
        image   = var.container_image
        command = ["alembic", "upgrade", "head"]

        env {
          name  = "DB_USER"
          value = google_sql_user.app.name
        }
        env {
          name  = "DB_NAME"
          value = google_sql_database.app.name
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.main.connection_name
        }
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_password.secret_id
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.main.connection_name]
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.enabled]
}
