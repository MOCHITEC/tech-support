# フィードバック/パイプライン段階イベントのトピックと DLQ。
resource "google_pubsub_topic" "events" {
  name       = "${var.name_prefix}-events"
  depends_on = [google_project_service.enabled]
}

resource "google_pubsub_topic" "dlq" {
  name       = "${var.name_prefix}-events-dlq"
  depends_on = [google_project_service.enabled]
}

# エージェントサービスへ OIDC 認証付きで push する。
resource "google_pubsub_subscription" "events_push" {
  name  = "${var.name_prefix}-events-push"
  topic = google_pubsub_topic.events.id

  ack_deadline_seconds = 60

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agents.uri}/pubsub/push"

    oidc_token {
      service_account_email = google_service_account.pubsub_push.email
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

# DLQ を読むためのサブスクリプション(運用確認用)。
resource "google_pubsub_subscription" "dlq_pull" {
  name  = "${var.name_prefix}-events-dlq-pull"
  topic = google_pubsub_topic.dlq.id
}

# Pub/Sub サービスエージェントに、push SA の OIDC トークン発行を許可する。
resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.pubsub_push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.pubsub_sa}"
}

# デッドレター配送のため、Pub/Sub サービスエージェントに DLQ への publish と購読の権限を付与。
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.dlq.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${local.pubsub_sa}"
}

resource "google_pubsub_subscription_iam_member" "events_subscriber" {
  subscription = google_pubsub_subscription.events_push.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_sa}"
}
