import json
from os import environ

from fastapi.openapi.utils import get_openapi

from src.main import app

with open(environ.get("FASTAPI_OPENAPI_OUTPUT", "openapi.json"), "w") as f:
    json.dump(
        get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        ),
        f,
    )
