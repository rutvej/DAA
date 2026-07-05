terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Cloud SQL (PostgreSQL Instance)
resource "google_sql_database_instance" "postgres" {
  name             = "daa-postgres-db"
  database_version = "POSTGRES_13"
  region           = var.region

  settings {
    tier = "db-f1-micro"
  }
  deletion_protection = false
}

resource "google_sql_database" "database" {
  name     = "yourdb"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "users" {
  name     = "youruser"
  instance = google_sql_database_instance.postgres.name
  password = "secure_password_here"
}

# 2. Cloud Run Service: Backend API
resource "google_cloud_run_service" "backend_api" {
  name     = "daa-backend-api"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/daa-backend-api:latest"
        env {
          name  = "DATABASE_URL"
          value = "postgresql://youruser:secure_password_here@${google_sql_database_instance.postgres.public_ip_address}/yourdb"
        }
        env {
          name  = "RABBITMQ_HOST"
          value = "rabbitmq-service-ip" # In production, configure Cloud AMQP or fully-managed RabbitMQ
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# 3. Cloud Run Service: Python Agent
resource "google_cloud_run_service" "python_agent" {
  name     = "daa-python-agent"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/daa-python-agent:latest"
        env {
          name  = "RABBITMQ_HOST"
          value = "rabbitmq-service-ip"
        }
        env {
          name  = "DAA_BACKEND_API_URL"
          value = google_cloud_run_service.backend_api.status[0].url
        }
        env {
          name  = "GEMINI_API_KEY"
          value = var.gemini_api_key
        }
        env {
          name  = "GITLAB_PRIVATE_TOKEN"
          value = var.gitlab_private_token
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Allow unauthenticated access to the backend-api
resource "google_cloud_run_service_iam_member" "noauth" {
  location = google_cloud_run_service.backend_api.location
  project  = google_cloud_run_service.backend_api.project
  service  = google_cloud_run_service.backend_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
