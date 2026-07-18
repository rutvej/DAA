# DAA Node.js SDK

The Node.js SDK for DAA (Dynamic Application Analytics) allows you to seamlessly capture and send exceptions and structured logs to your DAA backend.

## Installation

```bash
npm install daa-node-sdk
```
*(Note: Replace with the actual package name if published)*

## Usage

### Initialization

The `DaaSdk` constructor accepts an options object:

```javascript
const DaaSdk = require('daa-node-sdk');

const daa = new DaaSdk({
  backendUrl: 'http://localhost:8000', // Optional. Defaults to process.env.DAA_BACKEND_API_URL or 'http://localhost:8000'
  token: 'your-auth-token',            // Optional. Defaults to process.env.DAA_TOKEN
  appName: 'my-node-app'               // Optional. Defaults to process.env.REPO_NAME or 'default-node-app'
});
```

### Capturing Exceptions

To capture an exception and send its stack trace to the backend:

```javascript
try {
  // Your application logic here
  throw new Error("Something went wrong!");
} catch (error) {
  // Capture the error object directly
  daa.captureException(error);
}
```

### Sending Custom Logs

You can also send a custom log payload using `sendLog`:

```javascript
daa.sendLog({
  content: JSON.stringify({ message: "Custom log event" }),
  app_name: "my-node-app"
});
```

## Configuration

You can configure the SDK using environment variables:
- `DAA_BACKEND_API_URL`: The URL of your DAA backend (default: `http://localhost:8000`)
- `DAA_TOKEN`: Your authorization token
- `REPO_NAME`: The name of your application/repository (default: `default-node-app`)
