# Implementation and demo checklist

Use this checklist as the acceptance criteria before adding project claims to a CV.

## Milestone 1 — local control plane

- [ ] Create and activate a Python 3.11+ virtual environment.
- [ ] Install `.[dev,ui]` and run `pytest`.
- [ ] Start PostgreSQL and confirm the API creates the `releases` table.
- [ ] Create a kind cluster and install the CRD.
- [ ] Start the operator and API in separate terminals.
- [ ] Create a web application through `platformctl`.
- [ ] Verify the Application CR, target namespace, quota, limit range, Deployment and Service.

## Milestone 2 — lifecycle behavior

- [ ] Deploy version 1 of a test application.
- [ ] Deploy version 2 and verify the custom resource and workload image change.
- [ ] Roll back and verify the previous image/version is restored.
- [ ] Delete the Application and verify the operator removes its target namespace.
- [ ] Create the stateful sample and verify the StatefulSet, headless Service and PVC.
- [ ] Add a batch image with a known non-root user and verify Job completion.

## Milestone 3 — diagnostics and governance

- [ ] Deploy an intentionally invalid image tag and use `platformctl app diagnose` to identify the image-pull failure.
- [ ] Restore the valid image and verify the workload recovers.
- [ ] Install Kyverno and apply the example ClusterPolicies.
- [ ] Confirm a Pod missing CPU/memory limits is rejected.
- [ ] Confirm a Pod running as root or using `:latest` is rejected.
- [ ] Record the Kubernetes Events that explain each policy rejection.

## Milestone 4 — security and observability

- [ ] Verify Trivy scans both built container images in CI.
- [ ] Install kube-prometheus-stack and apply the ServiceMonitor.
- [ ] Confirm `platformctl_reconcile_total` and `platformctl_reconcile_seconds` appear in Prometheus.
- [ ] Import the Grafana dashboard and trigger a successful and failed reconciliation.
- [ ] Run the Streamlit status page and use its diagnostics action.

## Interview demo sequence

1. Register a web app using `platformctl app create`.
2. Show the Application CR and explain desired state versus reconciliation.
3. Show the operator creating a namespace, quota, Deployment and Service.
4. Deploy a second version, show release history and roll back.
5. Introduce a bad image and use diagnostics to identify `ImagePullBackOff`.
6. Show a Kyverno rejection and the corresponding event.
7. Finish with the Prometheus metrics and Grafana dashboard.

Do not describe an unchecked milestone as implemented. Capture terminal output, test results and screenshots as you complete each milestone.
