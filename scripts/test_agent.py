#!/usr/bin/env python3
"""Test the agent workflow from CLI.

Usage:
    # Generate a report (uses first project from seed data)
    python scripts/test_agent.py report

    # Query progress
    python scripts/test_agent.py query "目前整体进度如何？"

    # Specify project
    python scripts/test_agent.py report --project-id <id>
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def get_first_project_id() -> str:
    """Fetch the first project ID from the database."""
    import asyncio
    from sqlalchemy import text
    from app.db.mysql import get_session_factory

    async def _query():
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                text("SELECT id, name FROM projects WHERE is_deleted = 0 LIMIT 1")
            )
            row = result.first()
            if row:
                print(f"  {CYAN}→{RESET} Using project: {row[1]} ({row[0]})")
                return row[0]
            return ""

    return asyncio.get_event_loop().run_until_complete(_query())


def test_report(project_id: str):
    """Test report generation."""
    print(f"\n{BOLD}Report Generation Test{RESET}")
    print("─" * 50)

    from app.agents.graph import run_report_agent

    start = time.perf_counter()
    result = run_report_agent(project_id=project_id, user_id="test_user")
    elapsed = time.perf_counter() - start

    if result["success"]:
        print(f"  {GREEN}✓{RESET} Report generated in {elapsed:.1f}s")
        print(f"  {GREEN}✓{RESET} Title: {result['title']}")
        print(f"  {GREEN}✓{RESET} Content: {len(result['content'])} chars")
        print(f"  {GREEN}✓{RESET} Summary: {result['summary'][:200]}...")
        print(f"\n{BOLD}--- Report Preview ---{RESET}")
        print(result["content"][:1000])
        if len(result["content"]) > 1000:
            print(f"\n... ({len(result['content']) - 1000} more chars)")
    else:
        print(f"  {RED}✗{RESET} Failed: {result['error']}")
        return False

    return True


def test_query(project_id: str, question: str):
    """Test progress query."""
    print(f"\n{BOLD}Progress Query Test{RESET}")
    print("─" * 50)
    print(f"  {CYAN}→{RESET} Question: {question}")

    from app.agents.graph import run_query_agent

    start = time.perf_counter()
    result = run_query_agent(project_id=project_id, user_id="test_user", question=question)
    elapsed = time.perf_counter() - start

    if result["success"]:
        print(f"  {GREEN}✓{RESET} Answer in {elapsed:.1f}s")
        print(f"\n{BOLD}--- Answer ---{RESET}")
        print(result["answer"])
    else:
        print(f"  {RED}✗{RESET} Failed: {result['error']}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Test agent workflow")
    parser.add_argument("mode", choices=["report", "query"], help="Test mode")
    parser.add_argument("question", nargs="?", default="目前整体进度如何？", help="Question for query mode")
    parser.add_argument("--project-id", default="", help="Project ID (auto-detect if omitted)")
    args = parser.parse_args()

    project_id = args.project_id or get_first_project_id()
    if not project_id:
        print(f"  {RED}✗{RESET} No project found. Run 'python scripts/seed_data.py' first.")
        sys.exit(1)

    if args.mode == "report":
        ok = test_report(project_id)
    else:
        ok = test_query(project_id, args.question)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()