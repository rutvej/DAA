# DAA Go SDK

The Go SDK for DAA (Dynamic Application Analytics) makes it easy to capture exceptions (errors) and report logs to your DAA backend.

## Installation

```bash
go get github.com/your-org/daa-go-sdk
```
*(Note: Replace with your actual Go module path)*

## Usage

### Initialization

The `NewClient` function accepts configuration parameters. You can pass empty strings to let the SDK fall back to environment variables.

```go
import "path/to/daa"

// NewClient(backendURL, token, appName string)
client := daa.NewClient(
    "http://localhost:8000", // backendURL (fallback: DAA_BACKEND_API_URL or http://localhost:8000)
    "your-auth-token",       // token (fallback: DAA_TOKEN)
    "my-go-app",             // appName (fallback: REPO_NAME or default-go-app)
)
```

### Capturing Exceptions

To capture an error:

```go
_, err := os.Open("non-existent-file.txt")
if err != nil {
    // Passes the error object, extracts a stack trace and sends it to DAA
    _ = client.CaptureException(err)
}
```

### Sending Custom Logs

You can also send your own structured logs:

```go
payload := daa.LogPayload{
    Content: `{"message": "Custom event log"}`,
    AppName: "my-go-app",
}

err := client.SendLog(payload)
```

## Configuration

When empty strings are provided to `NewClient`, the SDK relies on:
- `DAA_BACKEND_API_URL`: The URL of your DAA backend
- `DAA_TOKEN`: Your authorization token
- `REPO_NAME`: The name of your application/repository
