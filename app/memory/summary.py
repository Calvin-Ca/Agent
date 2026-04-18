"""Summary memory — compress long conversation histories.

TODO: Implement conversation summarizer that:
1. Detects when conversation exceeds token limit
2. Summarizes older messages via LLM
3. Replaces message history with summary + recent messages
"""

from __future__ import annotations
