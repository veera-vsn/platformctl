from platformctl.operator.diagnostics import analyse_pods_and_events


def test_diagnose_crash_loop_and_oom_kill():
    report = analyse_pods_and_events([
        {"metadata": {"name": "api-0"}, "status": {"phase": "Running", "containerStatuses": [
            {"state": {"waiting": {"reason": "CrashLoopBackOff"}}, "ready": False, "restartCount": 4}
        ]}},
        {"metadata": {"name": "worker-0"}, "status": {"phase": "Running", "containerStatuses": [
            {"state": {"terminated": {"reason": "OOMKilled"}}, "ready": False, "restartCount": 1}
        ]}},
    ], [])
    assert not report["healthy"]
    assert {finding["reason"] for finding in report["findings"]} == {"CrashLoopBackOff", "OOMKilled"}


def test_diagnose_quota_and_policy_events():
    report = analyse_pods_and_events([], [
        {"type": "Warning", "reason": "FailedCreate", "message": "exceeded quota: app-quota"},
        {"type": "Warning", "reason": "PolicyViolation", "message": "Kyverno policy validation failed"},
    ])
    assert len(report["findings"]) == 2
    assert any("quota" in finding["message"].lower() for finding in report["findings"])
    assert any("admission policy" in finding["message"].lower() for finding in report["findings"])


def test_diagnose_healthy_pods():
    report = analyse_pods_and_events([
        {"metadata": {"name": "web-0"}, "status": {"phase": "Running", "containerStatuses": [
            {"state": {"running": {}}, "ready": True, "restartCount": 0}
        ]}}
    ], [])
    assert report["healthy"] is True


def test_diagnose_supports_kubernetes_python_client_snake_case_fields():
    report = analyse_pods_and_events([
        {"metadata": {"name": "api-1"}, "status": {"phase": "Running", "container_statuses": [
            {"state": {"waiting": {"reason": "ImagePullBackOff"}}, "ready": False, "restart_count": 0}
        ]}}
    ], [
        {"type": "Warning", "reason": "Unhealthy", "message": "Readiness probe failed: connection refused",
         "involved_object": {"name": "api-1"}}
    ])
    reasons = {finding["reason"] for finding in report["findings"]}
    assert "ImagePullBackOff" in reasons
    assert "Unhealthy" in reasons
    assert any("readiness probe is failing" in finding["message"].lower() for finding in report["findings"])
