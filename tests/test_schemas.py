import pytest
from pydantic import ValidationError

from platformctl.api.schemas import AppCreate


def test_application_schema_accepts_supported_workload_types():
    app = AppCreate.model_validate({"name": "orders", "type": "web", "image": "nginx:1.27", "version": "1.27"})
    assert app.app_type == "web"
    assert app.port == 8080


@pytest.mark.parametrize("name", ["Uppercase", "bad_name", "has space", "-leading"])
def test_application_name_must_be_dns_compatible(name):
    with pytest.raises(ValidationError):
        AppCreate.model_validate({"name": name, "type": "web", "image": "nginx:1.27", "version": "1.27"})
