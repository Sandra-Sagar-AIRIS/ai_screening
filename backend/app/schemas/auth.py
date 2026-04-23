from enum import StrEnum

from pydantic import BaseModel


class UserRole(StrEnum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    CLIENT_VIEWER = "client_viewer"


class CurrentUser(BaseModel):
    user_id: str
    organization_id: str
    role: UserRole | None = None

