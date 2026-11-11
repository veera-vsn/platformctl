import re
from copy import deepcopy
from typing import Any

DEFAULT_RESOURCES = {
    "requests": {"cpu": "100m", "memory": "128Mi"},
    "limits": {"cpu": "500m", "memory": "256Mi"},
}


def target_namespace(app_name: str) -> str:
    return f"app-{app_name}"[:63].rstrip("-")


def resolve_target_namespace(app_name: str, requested: str | None = None) -> str:
    namespace = requested or target_namespace(app_name)
    if not re.fullmatch(r"app-[a-z0-9]([-a-z0-9]*[a-z0-9])?", namespace):
        raise ValueError("targetNamespace must be a valid DNS label with the app- prefix")
    if len(namespace) > 63:
        raise ValueError("targetNamespace must be 63 characters or fewer")
    return namespace


def _labels(app_name: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": app_name,
        "app.kubernetes.io/managed-by": "platformctl",
        "platform.veera.dev/application": app_name,
    }


def _container(spec: dict[str, Any], app_name: str) -> dict[str, Any]:
    resources = deepcopy(spec.get("resources") or DEFAULT_RESOURCES)
    resources.setdefault("requests", DEFAULT_RESOURCES["requests"])
    resources.setdefault("limits", DEFAULT_RESOURCES["limits"])
    port = int(spec.get("port", 8080))
    return {
        "name": app_name,
        "image": spec["image"],
        "imagePullPolicy": "IfNotPresent",
        "ports": [{"name": "http", "containerPort": port, "protocol": "TCP"}],
        "resources": resources,
        "securityContext": {
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": False,
            "capabilities": {"drop": ["ALL"]},
        },
        "readinessProbe": {"tcpSocket": {"port": port}, "initialDelaySeconds": 5, "periodSeconds": 10},
        "livenessProbe": {"tcpSocket": {"port": port}, "initialDelaySeconds": 15, "periodSeconds": 20},
    }


def _pod_template(spec: dict[str, Any], app_name: str) -> dict[str, Any]:
    pod_security_context = {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    if spec.get("fsGroup") is not None:
        pod_security_context["fsGroup"] = int(spec["fsGroup"])
    return {
        "metadata": {"labels": _labels(app_name)},
        "spec": {
            "securityContext": pod_security_context,
            "containers": [_container(spec, app_name)],
        },
    }


def namespace_object(app_name: str, namespace: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1", "kind": "Namespace",
        "metadata": {"name": namespace, "labels": {
            "platform.veera.dev/managed": "true",
            "platform.veera.dev/application": app_name,
        }},
    }


def quota_object(namespace: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1", "kind": "ResourceQuota",
        "metadata": {"name": "platform-default-quota", "namespace": namespace},
        "spec": {"hard": {"requests.cpu": "2", "requests.memory": "2Gi",
                            "limits.cpu": "4", "limits.memory": "4Gi", "pods": "20"}},
    }


def limitrange_object(namespace: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1", "kind": "LimitRange",
        "metadata": {"name": "platform-default-limits", "namespace": namespace},
        "spec": {"limits": [{"type": "Container", "default": {"cpu": "500m", "memory": "256Mi"},
                              "defaultRequest": {"cpu": "100m", "memory": "128Mi"}}]},
    }


def service_object(app_name: str, namespace: str, port: int, headless: bool = False) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "selector": _labels(app_name),
        "ports": [{"name": "http", "port": port, "targetPort": "http", "protocol": "TCP"}],
    }
    if headless:
        spec["clusterIP"] = "None"
    return {"apiVersion": "v1", "kind": "Service",
            "metadata": {"name": app_name, "namespace": namespace, "labels": _labels(app_name)},
            "spec": spec}


def workload_objects(app_name: str, namespace: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    app_type = spec.get("type", "web")
    template = _pod_template(spec, app_name)
    selector = {"matchLabels": _labels(app_name)}
    if app_type == "web":
        deployment = {
            "apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": app_name, "namespace": namespace, "labels": _labels(app_name)},
            "spec": {"replicas": int(spec.get("replicas", 1)), "selector": selector,
                     "strategy": {"type": "RollingUpdate"}, "template": template},
        }
        return [deployment, service_object(app_name, namespace, int(spec.get("port", 8080)))]
    if app_type == "stateful":
        # Mount the PVC declared by volumeClaimTemplates into the application container.
        template["spec"]["containers"][0]["volumeMounts"] = [{
            "name": "data", "mountPath": spec.get("mountPath", "/var/lib/platformctl")
        }]
        stateful_set = {
            "apiVersion": "apps/v1", "kind": "StatefulSet",
            "metadata": {"name": app_name, "namespace": namespace, "labels": _labels(app_name)},
            "spec": {"serviceName": app_name, "replicas": int(spec.get("replicas", 1)),
                     "selector": selector, "template": template,
                     "volumeClaimTemplates": [{"metadata": {"name": "data"},
                         "spec": {"accessModes": ["ReadWriteOnce"],
                                  "resources": {"requests": {"storage": spec.get("storage", "1Gi")}}}}]},
        }
        return [stateful_set, service_object(app_name, namespace, int(spec.get("port", 8080)), headless=True)]
    if app_type == "batch":
        version_slug = re.sub(r"[^a-z0-9-]+", "-", str(spec.get("version", "run")).lower()).strip("-")[:20]
        job_name = f"{app_name}-{version_slug or 'run'}"[:63].rstrip("-")
        job = {
            "apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": job_name, "namespace": namespace, "labels": _labels(app_name)},
            "spec": {"backoffLimit": 2, "ttlSecondsAfterFinished": 86400,
                     "template": {"metadata": {"labels": _labels(app_name)},
                                  "spec": {"restartPolicy": "Never",
                                           "securityContext": template["spec"]["securityContext"],
                                           "containers": [{k: v for k, v in template["spec"]["containers"][0].items() if k != "ports" and k not in ("readinessProbe", "livenessProbe")}]} }},
        }
        return [job]
    raise ValueError(f"Unsupported application type: {app_type}")


def all_application_objects(app_name: str, spec: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    namespace = resolve_target_namespace(app_name, spec.get("targetNamespace"))
    base = [namespace_object(app_name, namespace), quota_object(namespace), limitrange_object(namespace)]
    return namespace, base + workload_objects(app_name, namespace, spec)
