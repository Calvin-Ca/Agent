"""V1 API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.project import router as project_router
from app.api.v1.report import router as report_router
from app.api.v1.progress import router as progress_router
from app.api.v1.upload import router as upload_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(project_router)
v1_router.include_router(report_router)
v1_router.include_router(progress_router)
v1_router.include_router(upload_router)