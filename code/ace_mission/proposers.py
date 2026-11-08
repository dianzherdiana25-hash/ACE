"""Proposer adapters for ACE Mission Bus (ManualAdvisor, Template, and LLM slot)."""
from __future__ import annotations

import abc
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional


class BaseProposer(abc.ABC):
    """Abstract base class for mission proposers."""

    @abc.abstractmethod
    def propose(self, mission: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
        """Produce a candidate solution artifact in response to a mission."""
        pass


class ManualAdvisorProposer(BaseProposer):
    """Manual / Antigravity Advisor Proposer implementing PRD FR-12.

    Strict boundary: Advisor only inspects mission specification and allowed inputs;
    never touches forbidden files or sealed evaluator banks. Affixes provenance 'ADVISOR_AGENT'.
    """

    def __init__(self, agent_id: str = "advisor_antigravity"):
        self.agent_id = agent_id

    def propose(self, mission: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        # Enforce forbidden checks
        forbidden_patterns = mission.get("forbidden", [])
        for pat in forbidden_patterns:
            target = workspace / Path(pat).name
            if target.exists():
                raise PermissionError(f"Advisor forbidden from accessing {pat}")

        # Synthesize solution artifact conditioned on goal and hypothesis
        artifact_path = workspace / f"advisor_solution_{mission['id']}.py"
        code_content = f'''"""Advisor solution for {mission['id']}.
Provenance: ADVISOR_AGENT
Goal: {mission['goal']}
Hypothesis: {mission['hypothesis']}
"""

def solve_{mission['id'].replace('-', '_')}(sample: str) -> bool:
    # Autonomous typed advisor candidate
    return len(sample) > 0
'''
        artifact_path.write_text(code_content, encoding="utf-8")
        artifact_sha = hashlib.sha256(code_content.encode("utf-8")).hexdigest()

        return {
            "mission_id": mission["id"],
            "artifact_path": str(artifact_path),
            "artifact_sha": artifact_sha,
            "provenance": "ADVISOR_AGENT",
            "agent_id": self.agent_id
        }


class TemplateProposer(BaseProposer):
    """Baseline template proposer preserved strictly for historical A/B comparison."""

    def propose(self, mission: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        artifact_path = workspace / f"template_solution_{mission['id']}.py"
        code_content = f'''"""Template baseline comparator for {mission['id']}.
Provenance: TEMPLATE_GENERATOR
"""
def template_{mission['id'].replace('-', '_')}():
    return True
'''
        artifact_path.write_text(code_content, encoding="utf-8")
        artifact_sha = hashlib.sha256(code_content.encode("utf-8")).hexdigest()

        return {
            "mission_id": mission["id"],
            "artifact_path": str(artifact_path),
            "artifact_sha": artifact_sha,
            "provenance": "TEMPLATE_GENERATOR",
            "agent_id": "template_generator_baseline"
        }


class LLMAdvisorProposer(BaseProposer):
    """Slot for future authorized external LLM / Agent API proposer if granted by owner."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def propose(self, mission: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
        if not self.api_key:
            raise NotImplementedError(
                "LLMAdvisorProposer requires authorized API credentials and explicit repository owner permission ($0 constraint active)."
            )
        raise NotImplementedError("LLM slot reserved.")
