package com.daa;

import com.google.gson.Gson;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

public class DaaClient {
    private final String backendUrl;
    private final String token;
    private final String appName;
    private final HttpClient httpClient;
    private final Gson gson;

    public DaaClient() {
        this(
            System.getenv("DAA_BACKEND_API_URL") != null ? System.getenv("DAA_BACKEND_API_URL") : "http://localhost:8000",
            System.getenv("DAA_TOKEN"),
            System.getenv("REPO_NAME") != null ? System.getenv("REPO_NAME") : "default-java-app"
        );
    }

    public DaaClient(String backendUrl, String token, String appName) {
        this.backendUrl = backendUrl;
        this.token = token;
        this.appName = appName;
        this.httpClient = HttpClient.newHttpClient();
        this.gson = new Gson();
    }

    public void captureException(Throwable throwable) {
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        throwable.printStackTrace(pw);
        String stackTrace = sw.toString();

        Map<String, Object> logContent = new HashMap<>();
        logContent.put("message", throwable.getMessage() != null ? throwable.getMessage() : throwable.toString());
        logContent.put("stack_trace", stackTrace);
        logContent.put("context", new HashMap<String, Object>());
        logContent.put("timestamp", Instant.now().toString());

        Map<String, String> payload = new HashMap<>();
        payload.put("content", gson.toJson(logContent));
        payload.put("app_name", this.appName);

        sendLog(payload);
    }

    public void sendLog(Map<String, String> payload) {
        try {
            String jsonPayload = gson.toJson(payload);
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(this.backendUrl + "/logs/"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(jsonPayload));

            if (this.token != null && !this.token.isEmpty()) {
                requestBuilder.header("Authorization", "Bearer " + this.token);
            }

            HttpResponse<String> response = httpClient.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                System.err.println("DAA Java SDK received error status from backend: " + response.statusCode() + " - " + response.body());
            }
        } catch (Exception e) {
            System.err.println("DAA Java SDK failed to send log: " + e.getMessage());
        }
    }
}
