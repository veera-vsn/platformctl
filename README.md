# platformctl — Self-Service Kubernetes Application Platform

A platform-engineering portfolio project exploring a self-service control plane for Kubernetes applications.

## Architecture

```text
Developer -> platformctl CLI -> FastAPI control plane -> Kubernetes Application CR
                                      |                         |
                                      v                         v
                                  PostgreSQL              Python operator
                                  release history               |
                                                                v
                                             Namespace, quota, limits, workloads
```

The API writes desired application state to a namespaced `Application` custom resource. A Kopf operator reconciles that resource into Kubernetes objects. The CLI calls the API for application lifecycle operations.

## Current implementation

- Kubernetes `Application` CRD for web, stateful and batch workloads.
- Python Kopf operator with reconciliation handlers.
- Resource generation for Namespace, ResourceQuota, LimitRange, Deployment, StatefulSet, Service and Job.
- FastAPI endpoints for application create, list, inspect, deploy, rollback, diagnostics, release history and delete.
- PostgreSQL-backed release history (SQLite fallback for local development).
- Typer-based `platformctl` CLI.
- Diagnostic analysis for common pod states, scheduling, quota, probe and admission-policy events.
- Python unit tests and Kubernetes manifests are being added alongside the implementation.

## Technology

Python, FastAPI, Typer, Kopf, Kubernetes Python client, Kubernetes CRDs, PostgreSQL, SQLAlchemy, Docker, Prometheus client.

## Local setup

Requires Python 3.11+, Docker, kubectl and a Kubernetes cluster with permission to install the CRD and create namespaces.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Configure `DATABASE_URL` if using PostgreSQL. For local SQLite development, the API defaults to `./platformctl.db`.

Apply the CRD and create the control-plane namespace:

```bash
kubectl apply -f config/crd/application.yaml
kubectl create namespace platform-system
```

Run the operator and API in separate terminals:

```bash
kopf run --all-namespaces src/platformctl/operator/main.py
uvicorn platformctl.api.main:app --reload
```

Install and use the CLI:

```bash
platformctl app create demo --type web --image nginxinc/nginx-unprivileged:1.27-alpine --version 1.27 --port 8080
platformctl app status demo
platformctl app diagnose demo
```

## Project status

This is an actively developed portfolio project, not a production-ready Kubernetes platform. Validate the operator and API against a live cluster before relying on end-to-end behavior. Review RBAC, authentication, admission policies, persistence, reconciliation edge cases and CI results before any production use.

## License

MIT
