"""Domain-specific Pydantic schemas."""

from app.schema_defs.chat import ChatRequest, ChatResponse, IntentResult
from app.schema_defs.progress import ProgressOut
from app.schema_defs.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schema_defs.report import ReportGenerate, ReportOut
from app.schema_defs.upload import UploadOut
from app.schema_defs.user import TokenOut, UserLogin, UserOut, UserRegister, UserUpdate

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "IntentResult",
    "ProgressOut",
    "ProjectCreate",
    "ProjectOut",
    "ProjectUpdate",
    "ReportGenerate",
    "ReportOut",
    "TokenOut",
    "UploadOut",
    "UserLogin",
    "UserOut",
    "UserRegister",
    "UserUpdate",
]
