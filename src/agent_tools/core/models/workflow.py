import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class Result:
    """Unified result protocol for workflow orchestrators."""

    status: Literal["success", "handoff", "error"]
    message: str
    workflow: str = ""
    next_step: str = ""  # Semantic label for the next logical activity (e.g., 'resolve_conflicts')
    resume_point: str = ""  # Machine-readable string to pass back to the orchestrator (e.g., '--point current_rebase')
    instruction: str = ""  # Specific, actionable instructions and explicit prohibitions for the LLM agent
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize result to JSON string."""

        def serialize(obj):
            if callable(obj):
                return f"<function {obj.__name__}>"
            return str(obj)

        return json.dumps(asdict(self), default=serialize, indent=2, ensure_ascii=False)

    @property
    def ok(self) -> bool:
        """Check if result is successful."""
        return self.status == "success"
