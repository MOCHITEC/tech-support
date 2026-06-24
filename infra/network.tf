# サンドボックス Job の egress を Google restricted APIs だけに制限するためのネットワーク。
resource "google_compute_network" "vpc" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.enabled]
}

resource "google_compute_subnetwork" "subnet" {
  name                     = "${var.name_prefix}-subnet"
  ip_cidr_range            = "10.10.0.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

# Serverless VPC Access コネクタ(Cloud Run / Job から VPC を経由させる)。
resource "google_vpc_access_connector" "connector" {
  name          = "${var.name_prefix}-conn"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
  depends_on    = [google_project_service.enabled]
}

# restricted.googleapis.com への経路(デフォルトゲートウェイ経由の固定 VIP)。
resource "google_compute_route" "restricted_apis" {
  name             = "${var.name_prefix}-restricted-apis"
  network          = google_compute_network.vpc.name
  dest_range       = var.restricted_apis_cidr
  next_hop_gateway = "default-internet-gateway"
  priority         = 100
}

# restricted APIs への egress のみ許可。
resource "google_compute_firewall" "allow_restricted_egress" {
  name      = "${var.name_prefix}-allow-restricted-egress"
  network   = google_compute_network.vpc.name
  direction = "EGRESS"
  priority  = 100

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  destination_ranges = [var.restricted_apis_cidr]
}

# それ以外の egress は全て拒否(インターネットへの通信遮断)。
resource "google_compute_firewall" "deny_all_egress" {
  name      = "${var.name_prefix}-deny-all-egress"
  network   = google_compute_network.vpc.name
  direction = "EGRESS"
  priority  = 65534

  deny {
    protocol = "all"
  }

  destination_ranges = ["0.0.0.0/0"]
}
