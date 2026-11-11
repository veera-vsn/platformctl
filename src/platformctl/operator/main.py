import logging

import kopf
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from prometheus_client import start_http_server

from platformctl.operator.reconciler import KubernetesReconciler, RECONCILES

GROUP = "platform.veera.dev"
VERSION = "v1alpha1"
PLURAL = "applications"
logger = logging.getLogger(__name__)


def _clients():
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()
    return KubernetesReconciler(client.CoreV1Api(), client.AppsV1Api(), client.BatchV1Api())


@kopf.on.startup()
def startup(settings: kopf.OperatorSettings, **_: object) -> None:
    settings.persistence.finalizer = "platform.veera.dev/finalizer"
    start_http_server(9102)
    logger.info("platformctl operator started; metrics listening on :9102")


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile(spec: dict, name: str, namespace: str, patch: kopf.Patch, **_: object) -> dict:
    try:
        target = _clients().reconcile(name, spec)
        patch.status["phase"] = "Ready"
        patch.status["targetNamespace"] = target
        patch.status["observedGeneration"] = _.get("meta", {}).get("generation")
        patch.status["conditions"] = [{"type": "Ready", "status": "True",
                                       "reason": "ReconciliationSucceeded",
                                       "message": "Application resources are present."}]
        return {"message": "Application reconciled", "namespace": target}
    except Exception as exc:  # Kopf retries failed handlers; status helps the CLI explain the state.
        RECONCILES.labels(result="error").inc()
        patch.status["phase"] = "Failed"
        patch.status["conditions"] = [{"type": "Ready", "status": "False",
                                       "reason": "ReconciliationFailed", "message": str(exc)[:500]}]
        logger.exception("Failed to reconcile %s/%s", namespace, name)
        raise


@kopf.on.delete(GROUP, VERSION, PLURAL)
def delete(spec: dict, name: str, **_: object) -> dict:
    namespace = _clients().delete_application_namespace(name, spec)
    logger.info("Deleted target namespace %s for application %s", namespace, name)
    return {"deletedNamespace": namespace}
