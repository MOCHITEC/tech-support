terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# GitHub のブランチ保護を Terraform で管理する場合のみ使用する(enable_github_branch_protection)。
provider "github" {
  owner = split("/", var.github_repository)[0]
  token = var.github_token
}
