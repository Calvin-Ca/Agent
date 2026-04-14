"""Tool: MySQL database queries — fetch project info, progress, documents.

Used by agent nodes to gather structured data.
All functions are sync (called from Celery worker or sync context).

NOTE: This module re-exports from app.tools.db_query for backward compatibility.
      New code should use tool_registry.execute("db.*") instead.
"""

from app.tools.db_query import (  # noqa: F401
    _query_project_info as get_project_info,
    _query_recent_progress as get_recent_progress,
    _query_document_list as get_document_list,
    _query_recent_reports as get_recent_reports,
)
