# DAA SDK System Overview

This document details the multi-language SDK design, exception capture mechanisms, and communication client architecture.

## 1. Multi-Language SDK Folder Structure

The SDK is designed to be injected into target microservice frameworks to stream errors directly to the DAA backend. It supports 6 programming languages, located under `/home/rutvej/Desktop/DAA/app/daa-sdk/`:

```
app/daa-sdk/
├── setup.py             # Python package setup
├── daa_sdk/
│   └── __init__.py      # Python SDK client implementation
├── node-sdk/
│   ├── index.js         # NodeJS SDK client
│   └── package.json     # NodeJS package config
├── go-sdk/
│   ├── daa.go           # Go SDK client
│   └── go.mod           # Go module file
├── java-sdk/
│   ├── pom.xml          # Maven project config
│   └── src/main/java/com/daa/DaaClient.java # Java client
├── dotnet-sdk/
│   ├── DaaClient.cs     # .NET SDK client
│   └── daa-sdk.csproj   # .NET project file
└── ruby-sdk/
    ├── daa.gemspec      # Ruby Gem specification
    └── lib/daa.rb       # Ruby client implementation
```

---

## 2. Ingestion Gateway Integrations

Each SDK client implements a core class (e.g. `DaaSdk` in Python/Node, `Client` in Go, `DaaClient` in Java/.NET) that handles exception capture:
1. **Error Interception**: Hooked into application middleware, global error handlers, or `try/catch` statements.
2. **Context Hydration**: Gathers timestamp, exception type, error message, and extracts full code tracebacks.
3. **Payload Construction**: Serializes diagnostic metrics into standard JSON blocks.
4. **API Transmission**: Sends HTTP POST requests to the backend `/logs/` route. The request includes the application authentication token `DAA_TOKEN` in the `Authorization: Bearer <Token>` header.
