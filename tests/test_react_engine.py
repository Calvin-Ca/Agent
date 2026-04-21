from __future__ import annotations

import pytest

from agent.core.agent_loop import AgentLoop
from agent.core.state import AgentState


async def _fake_handler(**kwargs):
    return {"ok": True, "prompt": kwargs["prompt"]}


@pytest.mark.asyncio
async def test_agent_loop_prepares_state_with_plan():
    loop = AgentLoop(chat_handler=_fake_handler)
    state = await loop.prepare_state(prompt="查看项目进度", file=None, user_id="u-1")

    assert isinstance(state, AgentState)
    assert state.intent
    assert state.plan
    assert state.trace
