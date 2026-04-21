"""Backward-compatible config facade."""

from __future__ import annotations

from agent.infra.config import AppSettings as Settings
from agent.infra.config import get_settings

__all__ = ["Settings", "get_settings"]
