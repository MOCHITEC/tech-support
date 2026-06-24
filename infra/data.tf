data "google_project" "this" {}

locals {
  pubsub_sa = "service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
