"""Layer 3: Planning — task decomposition and routing.

The planner determines task_type and validates required fields
before the workflow proceeds to data collection.

To add a new planner strategy:
1. Create a new module in this package (e.g. llm_planner.py)
2. Implement the Planner protocol from base.py
3. Update the import below or use runtime selection in orchestration/
"""

from app.agents.planner.base import Planner
from app.agents.planner.default_planner import planner_node

__all__ = ["Planner", "planner_node"]
