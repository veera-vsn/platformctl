# Architecture and design decisions

## Control plane versus reconciliation

The FastAPI service is the user-facing control plane. It validates requests, creates or patches the `Application` custom resource and records a release request in PostgreSQL. It does not directly create Deployments or Services. This keeps workload orchestration in the operator and makes the operator the single reconciliation path.

The Kopf operator watches `Application` resources. For each resource it creates a target namespace, a ResourceQuota, a LimitRange and the workload-specific resources. Reconciliation is idempotent: an existing object is patched, while a missing object is created.

## Application types

- `web`: Deployment plus ClusterIP Service.
- `stateful`: StatefulSet plus headless Service and a persistent volume claim template.
- `batch`: Job with bounded retries and TTL cleanup.

## Release and rollback model

Each create/deploy/rollback request is recorded as a release row containing the app name, version, image and request status. Rollback selects the newest historical image that differs from the currently desired image and patches the custom resource. This MVP records requested state, not confirmed rollout success; a later iteration should reconcile Kubernetes status conditions back into the release table.

## Security boundaries

The operator has cluster-scoped permissions because it creates per-application namespaces. The API should be given only the ability to read/write `Application` custom resources. Kyverno policies validate Pods in platform-managed namespaces. In a production design, add authentication, tenant identity, authorization, admission policy tests, audit events, network policies, secret references and restricted namespace deletion.

## Reliability considerations

- The Kubernetes API is the source of desired state.
- Operator reconciliation retries transient errors through Kopf.
- Readiness/liveness probes use TCP checks on the declared application port.
- Namespace quotas and limit ranges establish baseline resource controls.
- Metrics expose reconcile count and duration; the sample ServiceMonitor and Grafana dashboard chart reconcile rate and p95 duration.
- The diagnostic endpoint correlates common Pod states and warning Events into suggested next checks.
- Release rows are append-only request history; they are not yet a deployment-success ledger.
