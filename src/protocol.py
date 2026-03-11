import json
from dataclasses import dataclass, field, asdict
from typing import Literal, Dict, Any

@dataclass
class Result:
    """Unified result protocol for workflow orchestrators."""
    status: Literal["success", "paused", "error"]
    message: str
    workflow: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize result to JSON string."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    @property
    def ok(self) -> bool:
        """Check if result is successful."""
        return self.status == "success"

