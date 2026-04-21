"""Product-facing V1 API router."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(chat_router)
