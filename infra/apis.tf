# 必要な Google API を有効化する。
locals {
  services = [
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "compute.googleapis.com",
    "vpcaccess.googleapis.com",
    "aiplatform.googleapis.com", # Gemini API
    "dns.googleapis.com",        # サンドボックス VPC 内の Private DNS(restricted VIP 解決)
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  service            = each.value
  disable_on_destroy = false
}
