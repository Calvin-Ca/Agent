"""Jinja2 template loader for prompt management.

All .j2 templates live in agent/prompts/templates/.
Python modules only call load() / render() — never hardcode prompt text.

Usage:
    from agent.prompts.loader import render, load

    # Static prompts (no variables)
    system_text = load("system.j2")

    # Dynamic prompts
    prompt = render("report.j2", project_name="城南花园", week_start="2026-04-14", ...)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


@lru_cache(maxsize=64)
def load(name: str) -> str:
    """Load a static template (no variables) and return its text."""
    return _env.get_template(name).render()


def render(name: str, **kwargs) -> str:
    """Render a template with the given variables."""
    return _env.get_template(name).render(**kwargs)


def get_env() -> Environment:
    """Return the Jinja2 environment for advanced usage (e.g. custom filters)."""
    return _env
