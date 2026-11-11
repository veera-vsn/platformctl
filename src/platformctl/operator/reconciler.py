import logging
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException
from prometheus_client import Counter, Histogram

from platformctl.operator.objects import all_application_objects, resolve_target_namespace

logger = logging.getLogger(__name__)
RECONCILES = Counter("platformctl_reconcile_total", "Application reconcile attempts", ["result"])
RECONCILE_SECONDS = Histogram("platformctl_reconcile_seconds", "Application reconcile duration")


class KubernetesReconciler:
    """Idempotently reconciles an Application spec into Kubernetes resources."""

    def __init__(self, core: client.CoreV1Api, apps: client.AppsV1Api, batch: client.BatchV1Api):
        self.core = core
        self.apps = apps
        self.batch = batch

    def _create_or_patch(self, obj: dict[str, Any]) -> None:
        kind = obj["kind"]
        metadata = obj["metadata"]
        name = metadata["name"]
        namespace = metadata.get("namespace")
        if kind == "Namespace":
            try:
                self.core.read_namespace(name)
                self.core.patch_namespace(name, obj)
            except ApiException as exc:
                if exc.status != 404:
                    raise
                self.core.create_namespace(obj)
            return

        if kind == "ResourceQuota":
            self._namespaced(self.core.read_namespaced_resource_quota, self.core.patch_namespaced_resource_quota,
                             self.core.create_namespaced_resource_quota, name, namespace, obj)
        elif kind == "LimitRange":
            self._namespaced(self.core.read_namespaced_limit_range, self.core.patch_namespaced_limit_range,
                             self.core.create_namespaced_limit_range, name, namespace, obj)
        elif kind == "Service":
            self._namespaced(self.core.read_namespaced_service, self.core.patch_namespaced_service,
                             self.core.create_namespaced_service, name, namespace, obj)
        elif kind == "Deployment":
            self._namespaced(self.apps.read_namespaced_deployment, self.apps.patch_namespaced_deployment,
                             self.apps.create_namespaced_deployment, name, namespace, obj)
        elif kind == "StatefulSet":
            self._namespaced(self.apps.read_namespaced_stateful_set, self.apps.patch_namespaced_stateful_set,
                             self.apps.create_namespaced_stateful_set, name, namespace, obj)
        elif kind == "Job":
            self._namespaced(self.batch.read_namespaced_job, self.batch.patch_namespaced_job,
                             self.batch.create_namespaced_job, name, namespace, obj)
        else:
            raise ValueError(f"Unsupported Kubernetes object kind: {kind}")

    @staticmethod
    def _namespaced(read_fn, patch_fn, create_fn, name, namespace, body) -> None:
        try:
            read_fn(name, namespace)
            patch_fn(name, namespace, body)
        except ApiException as exc:
            if exc.status != 404:
                raise
            create_fn(namespace, body)

    @RECONCILE_SECONDS.time()
    def reconcile(self, app_name: str, spec: dict[str, Any]) -> str:
        namespace, objects = all_application_objects(app_name, spec)
        for obj in objects:
            self._create_or_patch(obj)
        RECONCILES.labels(result="success").inc()
        logger.info("Reconciled application %s into namespace %s", app_name, namespace)
        return namespace

    def delete_application_namespace(self, app_name: str, spec: dict[str, Any] | None = None) -> str:
        namespace = resolve_target_namespace(app_name, (spec or {}).get("targetNamespace"))
        try:
            self.core.delete_namespace(namespace, propagation_policy="Background")
        except ApiException as exc:
            if exc.status != 404:
                raise
        return namespace
