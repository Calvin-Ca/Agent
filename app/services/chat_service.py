"""Chat service — orchestrate intent recognition and dispatch.

Bridges the API layer with agent graphs and business logic.
The chat endpoint delegates to this service for intent-based routing.

TODO: Migrate handler logic from api/v1/chat.py into this service
to keep the API layer thin (validation + response only).
"""

from __future__ import annotations
