from typing import Any
def _field(obj: dict, camel: str, snake: str | None = None, default=None): return obj.get(camel, obj.get(snake or camel, default))
WAITING_CAUSES = {"CrashLoopBackOff": "The container keeps exiting. Inspect application logs and startup configuration.", "ImagePullBackOff": "Kubernetes cannot pull the image. Check image name, tag and registry credentials.", "ErrImagePull": "The image pull failed. Check image reference, registry reachability and credentials.", "CreateContainerConfigError": "Kubernetes could not build container configuration. Check referenced Secrets and ConfigMaps.", "InvalidImageName": "The image reference is invalid. Use a valid registry/repository:tag reference."}
def analyse_pods_and_events(pods: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []; affected_pods: set[str] = set()
    for pod in pods:
        metadata = pod.get("metadata", {}); pod_name = metadata.get("name", "unknown-pod"); status = pod.get("status", {}) or {}; phase = status.get("phase", "Unknown")
        for cs in _field(status, "containerStatuses", "container_statuses", []) or []:
            state = cs.get("state", {}) or {}; waiting = state.get("waiting", {}) or {}; terminated = state.get("terminated", {}) or {}; reason = waiting.get("reason") or terminated.get("reason")
            if reason in WAITING_CAUSES: findings.append({"pod": pod_name, "reason": reason, "message": WAITING_CAUSES[reason]}); affected_pods.add(pod_name)
            elif reason == "OOMKilled": findings.append({"pod": pod_name, "reason": reason, "message": "The container exceeded its memory limit. Review memory usage and limits."}); affected_pods.add(pod_name)
            elif not cs.get("ready", True) and _field(cs, "restartCount", "restart_count", 0) > 0: findings.append({"pod": pod_name, "reason": "ContainerNotReady", "message": "The container is repeatedly restarting or failing readiness. Inspect logs and probe configuration."}); affected_pods.add(pod_name)
        for condition in status.get("conditions", []) or []:
            if condition.get("type") == "PodScheduled" and condition.get("status") == "False": findings.append({"pod": pod_name, "reason": condition.get("reason", "NotScheduled"), "message": condition.get("message", "The scheduler could not place this pod. Check node capacity and scheduling constraints.")}); affected_pods.add(pod_name)
        if phase == "Pending" and pod_name not in affected_pods: findings.append({"pod": pod_name, "reason": "Pending", "message": "The pod has not started. Inspect scheduling events, resource quotas and image pulls."}); affected_pods.add(pod_name)
    for event in events:
        reason = event.get("reason", "Unknown"); message = event.get("message", "")
        if event.get("type", "") != "Warning": continue
        lowered = message.lower()
        if "readiness probe" in lowered: suggestion = "The readiness probe is failing. Check application port, startup time and probe configuration."
        elif "liveness probe" in lowered: suggestion = "The liveness probe is failing and may restart the container. Check startup time and health."
        elif "exceeded quota" in lowered or (reason in {"FailedCreate", "FailedScheduling"} and "quota" in lowered): suggestion = "A namespace quota was exceeded. Review ResourceQuota usage and requests/limits."
        elif "insufficient cpu" in lowered or "insufficient memory" in lowered: suggestion = "The cluster has insufficient allocatable resources. Check node capacity, requests and autoscaling."
        elif "policy" in lowered or "kyverno" in lowered or "violat" in lowered: suggestion = "An admission policy rejected the resource. Review Kyverno policy reports and Pod security settings."
        elif reason in {"FailedScheduling", "FailedCreate"}: suggestion = "Kubernetes could not schedule or create the workload. Inspect event details and namespace configuration."
        else: suggestion = message or "Inspect the Kubernetes warning event for more detail."
        obj = _field(event, "involvedObject", "involved_object", {}) or {}; findings.append({"pod": obj.get("name", "namespace"), "reason": reason, "message": suggestion, "detail": message})
    return {"healthy": len(findings) == 0, "podCount": len(pods), "findings": findings, "summary": "No common pod or warning-event failures detected." if not findings else f"Found {len(findings)} diagnostic finding(s)."}
