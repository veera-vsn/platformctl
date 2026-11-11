from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceValues(BaseModel):
    requests: dict[str, str] = Field(default_factory=lambda: {"cpu": "100m", "memory": "128Mi"})
    limits: dict[str, str] = Field(default_factory=lambda: {"cpu": "500m", "memory": "256Mi"})


class AppCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", min_length=1, max_length=50)
    app_type: Literal["web", "stateful", "batch"] = Field(alias="type")
    image: str = Field(min_length=3, max_length=512)
    version: str = Field(min_length=1, max_length=128)
    port: int = Field(default=8080, ge=1, le=65535)
    replicas: int = Field(default=1, ge=1, le=20)
    resources: ResourceValues = Field(default_factory=ResourceValues)


class DeployRequest(BaseModel):
    image: str = Field(min_length=3, max_length=512)
    version: str = Field(min_length=1, max_length=128)


class ReleaseResponse(BaseModel):
    id: int
    app_name: str
    version: str
    image: str
    status: str
    requested_at: str
