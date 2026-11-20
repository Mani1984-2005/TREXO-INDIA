from __future__ import annotations

from fastapi import APIRouter

from ..config import TOKEN_TTL_SECONDS
from ..schemas.domain import LoginInput, LoginResult
from ..security import ApiError, check_passcode, create_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResult)
def login(payload: LoginInput) -> dict:
    if not check_passcode(payload.password):
        raise ApiError("INVALID_CREDENTIALS", "Incorrect owner passcode", 401)
    return {"token": create_token("owner"), "expires_in": TOKEN_TTL_SECONDS, "token_type": "bearer"}
