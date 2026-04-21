from __future__ import annotations

from agent.memory.knowledge_graph import KnowledgeGraphStore
from agent.memory.conversation import ConversationMemoryStore, conversation_memory
from agent.memory.episodic import EpisodicMemoryStore
from agent.memory.summary import ConversationSummaryStore
from agent.memory.working import WorkingMemory


def test_working_memory_summary():
    memory = WorkingMemory(max_items=4)
    memory.append("user", "你好")
    memory.append("assistant", "你好，有什么可以帮你")

    assert "user: 你好" in memory.summary()


def test_knowledge_graph_query():
    graph = KnowledgeGraphStore()
    graph.add("project-a", "owner", "alice")

    results = graph.query(subject="project-a")

    assert len(results) == 1
    assert results[0].object == "alice"


def test_conversation_memory_build_messages_and_compaction():
    memory = ConversationMemoryStore(max_turns=6, max_tokens=64)
    memory.add_turn("sess-1", "user", "你好")
    memory.add_turn("sess-1", "assistant", "你好，我可以帮你查看项目情况。")
    memory.add_turn("sess-1", "user", "请总结一下最近的进度")

    messages = memory.build_messages("sess-1", system_prompt="你是助手", max_tokens=32)

    assert messages[0] == {"role": "system", "content": "你是助手"}
    assert messages[-1] == {"role": "user", "content": "请总结一下最近的进度"}

    summary = memory.summarize_and_compact("sess-1", keep_last_turns=1, max_summary_chars=80)
    compacted = memory.get_history("sess-1")

    assert summary
    assert len(compacted) == 2
    assert compacted[0].metadata["summary"] is True
    assert compacted[-1].content == "请总结一下最近的进度"


def test_episodic_memory_metrics_and_query():
    memory = EpisodicMemoryStore()
    memory.record(
        project_id="proj-1",
        task_type="report",
        outcome="success",
        strategy="Used progress records and report history",
        quality_score=8.0,
    )
    memory.record(
        project_id="proj-1",
        task_type="report",
        outcome="failure",
        strategy="Skipped progress records",
        quality_score=4.0,
        error_message="timeout",
    )

    recalled = memory.recall(project_id="proj-1", task_type="report", query="progress records", limit=1)

    assert len(recalled) == 1
    assert recalled[0].outcome == "success"
    assert memory.get_success_rate(project_id="proj-1", task_type="report") == 0.5
    assert memory.get_average_quality(project_id="proj-1", task_type="report") == 6.0


def test_summary_store():
    store = ConversationSummaryStore()
    result = store.summarize_messages(
        [
            {"role": "user", "content": "第一句"},
            {"role": "assistant", "content": "第二句"},
        ],
        max_chars=12,
    )

    assert result.truncated is True
