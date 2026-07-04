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
  # 新しい API は max_throughput か instance 数の指定が必須。
  min_instances = 2
  max_instances = 3
  depends_on    = [google_project_service.enabled]
}

# Private DNS: *.googleapis.com を restricted VIP に解決させる。これが無いと
# サンドボックスは storage.googleapis.com をパブリック IP に解決し、deny_all で遮断される。
resource "google_dns_managed_zone" "googleapis" {
  name        = "${var.name_prefix}-googleapis"
  dns_name    = "googleapis.com."
  description = "restricted.googleapis.com VIP への Private Google Access 用"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }

  depends_on = [google_project_service.enabled]
}

# restricted.googleapis.com → VIP(199.36.153.4/30 の 4 アドレス)。
resource "google_dns_record_set" "restricted_a" {
  name         = "restricted.googleapis.com."
  managed_zone = google_dns_managed_zone.googleapis.name
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"]
}

# それ以外の *.googleapis.com は restricted.googleapis.com に集約。
resource "google_dns_record_set" "wildcard_cname" {
  name         = "*.googleapis.com."
  managed_zone = google_dns_managed_zone.googleapis.name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["restricted.googleapis.com."]
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
