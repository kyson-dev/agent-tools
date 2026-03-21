import json
from dataclasses import dataclass, field, asdict
from typing import Literal, Dict, Any

@dataclass
class Result:
    """Unified result protocol for workflow orchestrators."""
    status: Literal["success", "handoff", "error"]
    message: str
    workflow: str = ""
    next_step: str = ""        # Semantic label for the next logical activity (e.g., 'resolve_conflicts')
    resume_point: str = ""     # Machine-readable string to pass back to the orchestrator (e.g., '--point current_rebase')
    instruction: str = ""      # Specific, actionable instructions for the LLM agent
    details: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize result to JSON string."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    @property
    def ok(self) -> bool:
        """Check if result is successful."""
        return self.status == "success"

