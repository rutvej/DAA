using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace Daa
{
    public class DaaClient
    {
        private readonly string _backendUrl;
        private readonly string _token;
        private readonly string _appName;
        private static readonly HttpClient HttpClient = new HttpClient();

        public DaaClient(string backendUrl = null, string token = null, string appName = null)
        {
            _backendUrl = backendUrl ?? Environment.GetEnvironmentVariable("DAA_BACKEND_API_URL") ?? "http://localhost:8000";
            _token = token ?? Environment.GetEnvironmentVariable("DAA_TOKEN");
            _appName = appName ?? Environment.GetEnvironmentVariable("REPO_NAME") ?? "default-dotnet-app";
        }

        public async Task CaptureExceptionAsync(Exception exception)
        {
            var logContent = new
            {
                message = exception.Message,
                stack_trace = exception.StackTrace ?? string.Empty,
                context = new Dictionary<string, object>(),
                timestamp = DateTime.UtcNow.ToString("o")
            };

            var payload = new
            {
                content = JsonSerializer.Serialize(logContent),
                app_name = _appName
            };

            await SendLogAsync(payload);
        }

        public async Task SendLogAsync(object payload)
        {
            try
            {
                var json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var request = new HttpRequestMessage(HttpMethod.Post, $"{_backendUrl}/logs/")
                {
                    Content = content
                };

                if (!string.IsNullOrEmpty(_token))
                {
                    request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
                }

                var response = await HttpClient.SendAsync(request);
                if (!response.IsSuccessStatusCode)
                {
                    var responseBody = await response.Content.ReadAsStringAsync();
                    Console.Error.WriteLine($"DAA .NET SDK error: {response.StatusCode} - {responseBody}");
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"DAA .NET SDK failed to send log: {ex.Message}");
            }
        }
    }
}
