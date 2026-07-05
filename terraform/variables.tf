variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID (for GCP deploy)"
  default     = "my-daa-project"
}

variable "region" {
  type        = string
  description = "The target cloud region (GCP, AWS, Azure)"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "production"
}

variable "gemini_api_key" {
  type        = string
  description = "Gemini API Key for the DAA Agent"
  sensitive   = true
}

variable "gitlab_private_token" {
  type        = string
  description = "GitLab API Access Token"
  sensitive   = true
  default     = ""
}
