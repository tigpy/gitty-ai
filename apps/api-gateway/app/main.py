import uvicorn
import os
import sys

# Ensure project root is in sys.path to find libs and services
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# If 'libs' namespace package was already loaded by Uvicorn/environment,
# its cached __path__ won't include our directory. We must insert it.
if 'libs' in sys.modules:
    libs_mod = sys.modules['libs']
    local_libs = os.path.join(project_root, "libs")
    if hasattr(libs_mod, "__path__") and local_libs not in libs_mod.__path__:
        if not isinstance(libs_mod.__path__, list):
            libs_mod.__path__ = list(libs_mod.__path__)
        libs_mod.__path__.insert(0, local_libs)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from libs.logging import configure_logging, get_logger
from libs.exceptions import GittyError
from app.core.config import settings
from app.core.container import ApplicationContainer
from app.api.router import router as api_router

# Initialize structured logging
configure_logging(settings.ENV)
logger = get_logger("api-gateway")

# Initialize and wire dependency injection container
container = ApplicationContainer()
container.config.from_dict(settings.model_dump())
container.wire(packages=["app.api.v1"])

from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI application
app = FastAPI(
    title="Gitty AI API Gateway",
    description="AI-Powered Repository Knowledge Graph Platform API Gateway",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(GittyError)
async def gitty_error_handler(request: Request, exc: GittyError):
    logger.error("Domain/Infrastructure Error occurred", message=exc.message, code=exc.code)
    return JSONResponse(
        status_code=400 if exc.code != "ENTITY_NOT_FOUND" else 404,
        content={"message": exc.message, "code": exc.code}
    )

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled Exception occurred", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred.", "code": "INTERNAL_SERVER_ERROR"}
    )

app.include_router(api_router)

if __name__ == "__main__":
    logger.info("Starting Gitty AI API Gateway", env=settings.ENV)
    uvicorn.run("apps.api-gateway.app.main:app", host="0.0.0.0", port=8000, reload=(settings.ENV == "development"))
