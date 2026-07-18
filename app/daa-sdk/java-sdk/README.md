# DAA Java SDK

The Java SDK for DAA (Dynamic Application Analytics) allows you to capture exceptions and log messages directly to your DAA backend.

## Installation

Ensure you have the package added to your project's dependencies (e.g., Maven or Gradle). The SDK relies on `com.google.code.gson:gson`.

## Usage

### Initialization

You can initialize `DaaClient` with specific parameters or rely on environment variables:

```java
import com.daa.DaaClient;

// Using explicit arguments
DaaClient daa = new DaaClient(
    "http://localhost:8000", // backendUrl
    "your-auth-token",       // token
    "my-java-app"            // appName
);

// OR using the default constructor (loads from environment variables)
DaaClient daaEnv = new DaaClient();
```

### Capturing Exceptions

To capture and report an exception:

```java
try {
    // Your application logic here
    int result = 1 / 0;
} catch (Exception e) {
    // Pass the Throwable object
    daa.captureException(e);
}
```

### Sending Custom Logs

To send custom log payloads:

```java
import java.util.HashMap;
import java.util.Map;

Map<String, String> payload = new HashMap<>();
payload.put("content", "{\"message\": \"Custom log\"}");
payload.put("app_name", "my-java-app");

daa.sendLog(payload);
```

## Configuration

When using the default constructor, the SDK relies on the following environment variables:
- `DAA_BACKEND_API_URL`: The backend URL (default: `http://localhost:8000`)
- `DAA_TOKEN`: Your authorization token
- `REPO_NAME`: The application name (default: `default-java-app`)
