from functools import lru_cache
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
def _load_config() -> None:
    try: config.load_incluster_config()
    except ConfigException: config.load_kube_config()
@lru_cache(maxsize=1)
def custom_objects_api() -> client.CustomObjectsApi:
    _load_config(); return client.CustomObjectsApi()
@lru_cache(maxsize=1)
def core_v1_api() -> client.CoreV1Api:
    _load_config(); return client.CoreV1Api()
