output "backend_api_url" {
  value       = google_cloud_run_service.backend_api.status[0].url
  description = "The URL of the deployed DAA Backend API"
}

output "python_agent_url" {
  value       = google_cloud_run_service.python_agent.status[0].url
  description = "The URL of the DAA Python Agent service"
}
