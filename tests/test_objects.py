from platformctl.operator.objects import all_application_objects, resolve_target_namespace, target_namespace, workload_objects


def test_web_application_renders_namespace_quota_deployment_and_service():
    spec = {"type": "web", "image": "nginxinc/nginx-unprivileged:1.27-alpine", "version": "1.27",
            "port": 8080, "replicas": 2}
    namespace, objects = all_application_objects("catalog", spec)
    assert namespace == "app-catalog"
    assert [item["kind"] for item in objects] == ["Namespace", "ResourceQuota", "LimitRange", "Deployment", "Service"]
    deployment = next(item for item in objects if item["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert deployment["spec"]["replicas"] == 2
    assert container["resources"]["limits"]["memory"] == "256Mi"
    assert container["securityContext"]["runAsNonRoot"] is True


def test_stateful_application_renders_persistent_volume_claim_template():
    objects = workload_objects("ledger", "app-ledger", {
        "type": "stateful", "image": "example/ledger:1.0", "version": "1.0", "port": 8080,
    })
    stateful_set = next(item for item in objects if item["kind"] == "StatefulSet")
    assert stateful_set["spec"]["volumeClaimTemplates"][0]["spec"]["resources"]["requests"]["storage"] == "1Gi"
    assert stateful_set["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]["mountPath"] == "/var/lib/platformctl"
    service = next(item for item in objects if item["kind"] == "Service")
    assert service["spec"]["clusterIP"] == "None"


def test_stateful_application_can_set_volume_group_for_writable_data():
    objects = workload_objects("cache", "app-cache", {
        "type": "stateful", "image": "redis:7.4-alpine", "version": "7.4",
        "port": 6379, "fsGroup": 999, "mountPath": "/data",
    })
    stateful_set = next(item for item in objects if item["kind"] == "StatefulSet")
    pod_spec = stateful_set["spec"]["template"]["spec"]
    assert pod_spec["securityContext"]["fsGroup"] == 999
    assert pod_spec["containers"][0]["volumeMounts"][0]["mountPath"] == "/data"


def test_batch_application_renders_job_without_http_probes():
    objects = workload_objects("reconcile", "app-reconcile", {
        "type": "batch", "image": "example/reconcile:2.0", "version": "2.0", "port": 8080,
    })
    assert len(objects) == 1
    container = objects[0]["spec"]["template"]["spec"]["containers"][0]
    assert "readinessProbe" not in container
    assert "livenessProbe" not in container
    assert objects[0]["kind"] == "Job"


def test_target_namespace_is_dns_length_safe():
    assert target_namespace("catalog") == "app-catalog"
    assert len(target_namespace("a" * 63)) <= 63


def test_target_namespace_must_be_platform_managed():
    import pytest

    with pytest.raises(ValueError):
        resolve_target_namespace("demo", "kube-system")
    with pytest.raises(ValueError):
        resolve_target_namespace("demo", "app-Invalid_Name")
