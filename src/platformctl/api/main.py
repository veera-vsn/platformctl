import os
from typing import Any
from fastapi import Depends, FastAPI, HTTPException, status
from kubernetes.client.rest import ApiException
from sqlalchemy import select
from sqlalchemy.orm import Session
from platformctl.api.database import get_db, init_db
from platformctl.api.kube import core_v1_api, custom_objects_api
from platformctl.api.models import Release
from platformctl.operator.diagnostics import analyse_pods_and_events
from platformctl.operator.objects import resolve_target_namespace
from platformctl.api.schemas import AppCreate, DeployRequest

GROUP, VERSION, PLURAL = "platform.veera.dev", "v1alpha1", "applications"
PLATFORM_NAMESPACE = os.getenv("PLATFORM_NAMESPACE", "platform-system")
app = FastAPI(title="platformctl control plane", version="0.1.0", description="Self-service Kubernetes application lifecycle API.")

@app.on_event("startup")
def startup() -> None:
    init_db()

def _kube_error(exc: ApiException) -> HTTPException:
    if exc.status == 404: return HTTPException(status_code=404, detail="Application not found")
    if exc.status == 409: return HTTPException(status_code=409, detail="Application already exists or is changing")
    return HTTPException(status_code=502, detail=f"Kubernetes API error ({exc.status}): {exc.reason}")

def _read_application(name: str) -> dict[str, Any]:
    try: return custom_objects_api().get_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL, name)
    except ApiException as exc: raise _kube_error(exc) from exc

def _record_release(db: Session, name: str, version: str, image: str, status_value: str) -> Release:
    release = Release(app_name=name, version=version, image=image, status=status_value)
    db.add(release); db.commit(); db.refresh(release)
    return release

@app.get("/healthz")
def healthz() -> dict[str, str]: return {"status": "ok"}

@app.get("/v1/apps")
def list_apps() -> dict[str, Any]:
    try:
        result = custom_objects_api().list_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL)
        return {"items": result.get("items", [])}
    except ApiException as exc: raise _kube_error(exc) from exc

@app.post("/v1/apps", status_code=status.HTTP_201_CREATED)
def create_app(payload: AppCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    body = {"apiVersion": f"{GROUP}/{VERSION}", "kind": "Application", "metadata": {"name": payload.name, "namespace": PLATFORM_NAMESPACE}, "spec": {"type": payload.app_type, "image": payload.image, "version": payload.version, "port": payload.port, "replicas": payload.replicas, "resources": payload.resources.model_dump()}}
    try: created = custom_objects_api().create_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL, body)
    except ApiException as exc: raise _kube_error(exc) from exc
    _record_release(db, payload.name, payload.version, payload.image, "REQUESTED")
    return created

@app.get("/v1/apps/{name}")
def get_app(name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    resource = _read_application(name)
    releases = db.scalars(select(Release).where(Release.app_name == name).order_by(Release.requested_at.desc())).all()
    resource["releaseHistory"] = [{"version": row.version, "image": row.image, "status": row.status, "requestedAt": row.requested_at.isoformat()} for row in releases]
    return resource

@app.post("/v1/apps/{name}/deploy")
def deploy_app(name: str, payload: DeployRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    current = _read_application(name); current.setdefault("spec", {})["image"] = payload.image; current["spec"]["version"] = payload.version
    try: updated = custom_objects_api().patch_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL, name, current)
    except ApiException as exc: raise _kube_error(exc) from exc
    _record_release(db, name, payload.version, payload.image, "REQUESTED")
    return updated

@app.post("/v1/apps/{name}/rollback")
def rollback_app(name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    current = _read_application(name)
    history = db.scalars(select(Release).where(Release.app_name == name).order_by(Release.requested_at.desc(), Release.id.desc())).all()
    previous = next((item for item in history if item.image != current.get("spec", {}).get("image")), None)
    if previous is None: raise HTTPException(status_code=409, detail="No earlier release is available to roll back to")
    current["spec"]["image"] = previous.image; current["spec"]["version"] = previous.version
    try: updated = custom_objects_api().patch_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL, name, current)
    except ApiException as exc: raise _kube_error(exc) from exc
    _record_release(db, name, previous.version, previous.image, "ROLLBACK_REQUESTED")
    return updated

@app.get("/v1/apps/{name}/diagnose")
def diagnose_app(name: str) -> dict[str, Any]:
    resource = _read_application(name)
    target = resolve_target_namespace(name, resource.get("status", {}).get("targetNamespace") or resource.get("spec", {}).get("targetNamespace"))
    try:
        core = core_v1_api(); pods = [item.to_dict() for item in core.list_namespaced_pod(target).items]; events = [item.to_dict() for item in core.list_namespaced_event(target).items]
    except ApiException as exc: raise HTTPException(status_code=502, detail=f"Kubernetes diagnostic query failed ({exc.status}): {exc.reason}") from exc
    return {"application": name, "namespace": target, "diagnostics": analyse_pods_and_events(pods, events)}

@app.get("/v1/apps/{name}/releases")
def list_releases(name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Release).where(Release.app_name == name).order_by(Release.requested_at.desc(), Release.id.desc())).all()
    return {"items": [{"id": row.id, "app_name": row.app_name, "version": row.version, "image": row.image, "status": row.status, "requested_at": row.requested_at.isoformat()} for row in rows]}

@app.delete("/v1/apps/{name}", status_code=status.HTTP_202_ACCEPTED)
def delete_app(name: str) -> dict[str, str]:
    try: custom_objects_api().delete_namespaced_custom_object(GROUP, VERSION, PLATFORM_NAMESPACE, PLURAL, name)
    except ApiException as exc: raise _kube_error(exc) from exc
    return {"status": "deletion requested", "application": name}
