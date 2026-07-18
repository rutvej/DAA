# DAA .NET SDK

The .NET SDK for DAA (Dynamic Application Analytics) helps you capture exceptions and send application logs to your DAA backend seamlessly.

## Installation

Add the DAA package to your project.
```bash
dotnet add package Daa
```

## Usage

### Initialization

The `DaaClient` constructor accepts optional arguments. If omitted, they fall back to environment variables.

```csharp
using Daa;

// DaaClient(string backendUrl = null, string token = null, string appName = null)
var daa = new DaaClient(
    backendUrl: "http://localhost:8000", // Optional. Defaults to DAA_BACKEND_API_URL or "http://localhost:8000"
    token: "your-auth-token",            // Optional. Defaults to DAA_TOKEN
    appName: "my-dotnet-app"             // Optional. Defaults to REPO_NAME or "default-dotnet-app"
);
```

### Capturing Exceptions

Use the asynchronous `CaptureExceptionAsync` method to log exceptions:

```csharp
try
{
    // Your application logic here
    throw new InvalidOperationException("Something went wrong!");
}
catch (Exception ex)
{
    // Await the asynchronous capture call
    await daa.CaptureExceptionAsync(ex);
}
```

### Sending Custom Logs

You can also send a custom payload asynchronously using `SendLogAsync`:

```csharp
var payload = new
{
    content = "{\"message\": \"Custom log event\"}",
    app_name = "my-dotnet-app"
};

await daa.SendLogAsync(payload);
```

## Configuration

If parameters are not provided to the constructor, the SDK relies on the following environment variables:
- `DAA_BACKEND_API_URL`: The backend URL
- `DAA_TOKEN`: Your authorization token
- `REPO_NAME`: The application name
