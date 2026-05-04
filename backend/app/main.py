from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import get_settings
from app.candidate_management.api import router as candidate_management_router
from app.models import reflect_database_schema
from app.routes.auth import router as auth_router
from app.routes.candidate import router as candidate_router
from app.routes.client import router as client_router
from app.routes.health import router as health_router
from app.routes.interview import router as interview_router
from app.routes.invites import router as invites_router
from app.routes.job import router as job_router
from app.routes.me import router as me_router
from app.routes.pipeline import pipeline_router as pipeline_singular_router
from app.routes.pipeline import router as pipeline_router
from app.routes.application import router as application_router
from app.routes.roles import router as roles_router
from app.routes.users import router as users_router

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Step 2: ADD CORS (TOP LEVEL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "http://localhost:3000",
    "Access-Control-Allow-Credentials": "true",
}

from fastapi.exceptions import RequestValidationError, ResponseValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        headers=CORS_HEADERS,
        content={
            "success": False,
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    return JSONResponse(
        status_code=500,
        headers=CORS_HEADERS,
        content={
            "success": False,
            "detail": "Response validation error. Data format mismatch.",
            "error": str(exc.errors())
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API exception", extra={"path": str(request.url.path), "method": request.method})
    return JSONResponse(
        status_code=500,
        headers=CORS_HEADERS,
        content={
            "success": False,
            "detail": "Internal server error",
            "error": str(exc)
        }
    )

# Reflect once at startup so ORM classes are available for repositories/services.
@app.on_event("startup")
def startup_event() -> None:
    reflect_database_schema()


app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(candidate_router, prefix="/api/v1")
app.include_router(candidate_management_router, prefix="/api/v1/candidate-management")
app.include_router(client_router, prefix="/api/v1")
app.include_router(job_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(pipeline_singular_router, prefix="/api/v1")
app.include_router(application_router, prefix="/api/v1")
app.include_router(interview_router, prefix="/api/v1")
app.include_router(invites_router, prefix="/api/v1/invites", tags=["invites"])
app.include_router(roles_router, prefix="/api/v1/roles", tags=["roles"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

