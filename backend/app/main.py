from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_cors_origins, get_settings
from app.models import reflect_database_schema
from app.routes.auth import router as auth_router
from app.routes.candidate import router as candidate_router
from app.routes.client import router as client_router
from app.routes.health import router as health_router
from app.routes.interview import router as interview_router
from app.routes.invites import router as invites_router
from app.routes.job import router as job_router
from app.routes.me import router as me_router
from app.routes.pipeline import router as pipeline_router
from app.routes.roles import router as roles_router
from app.routes.users import router as users_router

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Reflect once at startup so ORM classes are available for repositories/services.
@app.on_event("startup")
def startup_event() -> None:
    reflect_database_schema()


app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(candidate_router, prefix="/api/v1")
app.include_router(client_router, prefix="/api/v1")
app.include_router(job_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(interview_router, prefix="/api/v1")
app.include_router(invites_router, prefix="/api/v1/invites", tags=["invites"])
app.include_router(roles_router, prefix="/api/v1/roles", tags=["roles"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

