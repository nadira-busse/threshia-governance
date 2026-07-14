"""
ToolCall model.

Represents a single tool call proposed by an AI agent.
This is the input to the governance engine — the thing being evaluated.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolCall:
    """A tool call proposed by an AI agent for governance evaluation.

    Attributes:
        tool_name: The name of the tool the agent wants to call
                   (e.g. "transfer_funds", "query_database").
        parameters: The arguments the agent wants to pass to the tool.
        agent_id: Identifier for the agent making the call.
                  Default "demo-agent" for prototype scope.
        timestamp: When the tool call was proposed.
    """

    tool_name: str
    parameters: dict[str, Any]
    agent_id: str = "demo-agent"
    timestamp: datetime = field(default_factory=datetime.now)
