from enum import StrEnum

from pydantic import BaseModel


class UserType(StrEnum):
    INTERNAL = "internal"
    CLIENT = "client"


class CurrentUser(BaseModel):
    user_id: str
    organization_id: str
    role: str | None = None
    type: str = UserType.INTERNAL

