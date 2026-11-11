import json, os
from typing import Optional
import requests, typer
app = typer.Typer(no_args_is_help=True, help="Self-service Kubernetes application platform CLI")
app_group = typer.Typer(no_args_is_help=True, help="Manage applications")
app.add_typer(app_group, name="app")
def _request(method: str, path: str, payload: Optional[dict] = None) -> None:
    base = os.getenv("PLATFORMCTL_API_URL", "http://localhost:8000").rstrip("/")
    try:
        response = requests.request(method, f"{base}{path}", json=payload, timeout=20); response.raise_for_status()
    except requests.RequestException as exc:
        detail = exc.response.text if getattr(exc, "response", None) is not None else str(exc)
        typer.echo(f"platformctl: {detail}", err=True); raise typer.Exit(code=1) from exc
    try: typer.echo(json.dumps(response.json(), indent=2, default=str))
    except ValueError: typer.echo(response.text)
@app_group.command("create")
def create(name: str, app_type: str = typer.Option("web", "--type", help="web, stateful or batch"), image: str = typer.Option(..., "--image"), version: str = typer.Option(..., "--version"), port: int = typer.Option(8080, "--port"), replicas: int = typer.Option(1, "--replicas")) -> None:
    """Register an application and request its first deployment."""
    _request("POST", "/v1/apps", {"name": name, "type": app_type, "image": image, "version": version, "port": port, "replicas": replicas})
@app_group.command("deploy")
def deploy(name: str, image: str = typer.Option(..., "--image"), version: str = typer.Option(..., "--version")) -> None: _request("POST", f"/v1/apps/{name}/deploy", {"image": image, "version": version})
@app_group.command("status")
def status(name: str) -> None: _request("GET", f"/v1/apps/{name}")
@app_group.command("rollback")
def rollback(name: str) -> None: _request("POST", f"/v1/apps/{name}/rollback")
@app_group.command("diagnose")
def diagnose(name: str) -> None: _request("GET", f"/v1/apps/{name}/diagnose")
@app_group.command("releases")
def releases(name: str) -> None: _request("GET", f"/v1/apps/{name}/releases")
@app_group.command("delete")
def delete(name: str, yes: bool = typer.Option(False, "--yes", "-y", help="Confirm deletion")) -> None:
    if not yes: typer.confirm(f"Delete application '{name}' and its namespace?", abort=True)
    _request("DELETE", f"/v1/apps/{name}")
if __name__ == "__main__": app()
