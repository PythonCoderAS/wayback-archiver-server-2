import json
from os import environ
import warnings

from fastapi.openapi.utils import get_openapi

from src.main import app
from src.routes import load_routes

load_routes()

with open(environ.get("FASTAPI_OPENAPI_OUTPUT", "openapi.json"), "w") as f:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
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
