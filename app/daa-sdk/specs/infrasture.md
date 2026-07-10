# DAA SDK Infrastructure Specification

This document details the library packaging definitions, compilation prerequisites, and network communication channels for the DAA SDKs.

## 1. Packaging Files by Platform

Each language SDK is packaged using standard platform package managers:

- **Python SDK**:
  - Configured via `setup.py` at `/home/rutvej/Desktop/DAA/app/daa-sdk/setup.py`.
  - Installs the module as `daa-sdk`.
- **NodeJS SDK**:
  - Defined in `package.json`. Sets `axios` as a dependency.
- **Go SDK**:
  - Configured using `go.mod`. Binds Go versions `>= 1.16` and uses standard library features (zero external dependencies).
- **Java SDK**:
  - Managed by Maven configuration `pom.xml`. Defines target compiler, packaging formats, and GSON/Jackson dependencies.
- **Ruby SDK**:
  - Specified via `daa.gemspec` gem descriptor.
- **.NET SDK**:
  - Defined in project file `daa-sdk.csproj`.

---

## 2. Dynamic Integration Variables

Applications integrating the SDK require environment configurations to establish communication:

- **`DAA_BACKEND_API_URL`**: Target endpoint.
- **`DAA_TOKEN`**: Authorization Bearer token key.
- **`REPO_NAME`**: Name of the client service.

In Docker compose or Kubernetes manifests, these environment parameters are injected into the microservice containers:
```yaml
environment:
  - DAA_BACKEND_API_URL=http://daa-backend-api-service:80
  - DAA_TOKEN=daa-application-token-value
  - REPO_NAME=payment-service
```

---

## 3. Network Egress Layout

To transmit exception telemetry:
- **Egress Requirement**: The host application requires egress routing access to the Backend API container on the designated port (default: HTTP port `80` or host port `8000`).
- **Load Balancer/Proxy Support**: In cluster environments, the URL can point to internal ingress routers or service meshes (e.g. `http://daa-backend-api.daa-system.svc.cluster.local`).
