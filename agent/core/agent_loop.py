"""Main orchestrator for the refactored agent platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import UploadFile

from agent.input.guardrails import Guardrails
from agent.input.intent_router import IntentRouter
from agent.input.preprocessor import MessagePreprocessor
from agent.planning.planner import TaskPlanner
from agent.core.react_engine import ReActEngine
from agent.planning.reflector import Reflector
from agent.core.state import AgentState
from agent.output.formatter import ResponseFormatter
from agent.output.output_guard import OutputGuard


class AgentLoop:
    """Coordinate input normalization, planning, and execution."""

    def __init__(
        self,
        chat_handler: Callable[..., Awaitable[Any]],
        preprocessor: MessagePreprocessor | None = None,
        guardrails: Guardrails | None = None,
        intent_router: IntentRouter | None = None,
        planner: TaskPlanner | None = None,
        react_engine: ReActEngine | None = None,
        reflector: Reflector | None = None,
        formatter: ResponseFormatter | None = None,
        output_guard: OutputGuard | None = None,
    ) -> None:
        self.chat_handler = chat_handler
        self.preprocessor = preprocessor or MessagePreprocessor()
        self.guardrails = guardrails or Guardrails()
        self.intent_router = intent_router or IntentRouter()
        self.planner = planner or TaskPlanner()
        self.react_engine = react_engine or ReActEngine()
        self.reflector = reflector or Reflector()
        self.formatter = formatter or ResponseFormatter()
        self.output_guard = output_guard or OutputGuard()

    async def prepare_state(
        self,
        prompt: str,
        file: UploadFile | None,
        user_id: str,
    ) -> AgentState:
        message = self.preprocessor.normalize(prompt=prompt, file=file) # 把原始输入整理成统一的消息对象
        message = self.guardrails.validate(message)   # 对消息做校验或安全检查
        routed = await self.intent_router.route(message)
        state = AgentState(               # 根据意图路由生成状态
            user_id=user_id,
            message=message,
            user_input=message.content,
            intent=routed.intent,
            params=routed.params,
            metadata={"confidence": routed.confidence},
        )
        plan = self.planner.build(state)  # 根据当前状态生成执行计划
        return await self.react_engine.run(state, plan)  # 按计划进一步运行推理/执行逻辑，并返回更新后的 state

    async def handle_chat(
        self,
        *,
        db: Any,
        user: Any,
        prompt: str,
        file: UploadFile | None = None,
        state: AgentState | None = None,
    ) -> Any:
        # prepare_state runs: preprocessor → guardrails → intent_router → planner → react_engine
        # The resolved intent/params live in state — pass state to the handler to avoid re-running
        # intent recognition a second time.
        state = state or await self.prepare_state(prompt=prompt, file=file, user_id=str(user.id))

        try:
            result = await self.chat_handler(
                db=db,
                user=user,
                state=state,
                file=file,
            )
        except Exception as exc:
            state.reflections = self.reflector.reflect(state, error=exc) # 记录反思/错误信息，然后继续把异常抛出去，不吞掉错误
            raise

        formatted = self.formatter.format(result=result, state=state)
        guarded = self.output_guard.validate(formatted)
        state.final_result = guarded
        return guarded
