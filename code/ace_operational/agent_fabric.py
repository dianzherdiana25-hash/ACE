"""ACE local-model planner + bounded Codex/Antigravity worker fabric.

Proof-of-integration, NOT AGI, independent reasoning, free provider access,
unrestricted autonomy, or independent scientific evaluation. An Ollama model
suggests structured work orders, but the host validates them and retains all
authority. Worker tasks require explicit launch authorization and an isolated
Git worktree; writes additionally require an explicit scope and host verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit


WORKER_NAMES = frozenset({"codex", "antigravity"})
WORKER_MODES = frozenset({"read-only", "workspace-write"})
MAX_ORDERS = 8
MAX_GOAL_CHARS = 10000
MAX_PROMPT_CHARS = 6000
MAX_RESPONSE_BYTES = 262144

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "orders": {
            "type": "array", "minItems": 1, "maxItems": MAX_ORDERS,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "worker": {"type": "string", "enum": sorted(WORKER_NAMES)},
                    "mode": {"type": "string", "enum": sorted(WORKER_MODES)},
                    "instruction": {"type": "string"},
                    "depends_on": {
                        "type": "array", "items": {"type": "string"}
                    },
                },
                "required": ["id", "worker", "mode", "instruction", "depends_on"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["orders"],
    "additionalProperties": False,
}


def canonical(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(data: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkOrder:
    order_id: str
    worker: str
    mode: str
    instruction: str
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class WorkPlan:
    goal: str
    orders: tuple[WorkOrder, ...]
    planner: str

    @property
    def plan_digest(self) -> str:
        return digest({
            "goal": self.goal, "planner": self.planner,
            "orders": [
                {"id": o.order_id, "worker": o.worker, "mode": o.mode,
                 "instruction": o.instruction, "depends_on": list(o.depends_on)}
                for o in self.orders
            ],
        })


def validate_work_plan(goal: str, payload: Mapping[str, Any], *, planner: str) -> WorkPlan:
    """Treat model content strictly as a proposal, not host authorization."""
    if not isinstance(goal, str) or not 0 < len(goal.strip()) <= MAX_GOAL_CHARS:
        raise ValueError("goal must be 1..10000 characters")
    if not isinstance(payload, Mapping) or set(payload) != {"orders"}:
        raise ValueError("planner response must contain only orders")
    raw = payload["orders"]
    if type(raw) is not list or not 1 <= len(raw) <= MAX_ORDERS:
        raise ValueError("orders must contain 1..8 items")
    if not isinstance(planner, str) or not planner.strip():
        raise ValueError("planner ID required")

    orders = []
    prior_ids = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != {
            "id", "worker", "mode", "instruction", "depends_on"
        }:
            raise ValueError(f"invalid fields in order {index}")
        order_id, worker, mode = item["id"], item["worker"], item["mode"]
        instruction, deps = item["instruction"], item["depends_on"]
        if (not isinstance(order_id, str) or not order_id.isidentifier()
                or len(order_id) > 64 or order_id in prior_ids):
            raise ValueError("order IDs must be distinct identifiers")
        if worker not in WORKER_NAMES or mode not in WORKER_MODES:
            raise ValueError("unknown worker/mode")
        if (not isinstance(instruction, str)
                or not 0 < len(instruction.strip()) <= MAX_PROMPT_CHARS):
            raise ValueError("instruction outside permitted length")
        if (type(deps) is not list or len(deps) != len(set(deps))
                or any(not isinstance(d, str) or d not in prior_ids for d in deps)):
            raise ValueError("dependency must refer to an earlier distinct order")
        orders.append(WorkOrder(order_id, worker, mode, instruction, tuple(deps)))
        prior_ids.add(order_id)
    return WorkPlan(goal=goal, orders=tuple(orders), planner=planner)


class OllamaLocalPlanner:
    """Strict loopback Ollama /api/chat client; no API keys or remote URLs.

    This only asks an already-running local model to PRODUCE a work plan. It
    never invokes a subprocess, issues Git writes, or executes a proposed tool.
    """

    def __init__(
        self, *, model: str = "qwen3-coder",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        timeout_sec: int = 90,
        max_steps: int = 4,
    ) -> None:
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname not in
                {"127.0.0.1", "localhost", "::1"}
                or parsed.path != "/api/chat" or parsed.query or parsed.fragment
                or parsed.username or parsed.password):
            raise ValueError("Ollama endpoint must be local /api/chat")
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("model name required")
        if type(timeout_sec) is not int or not 1 <= timeout_sec <= 600:
            raise ValueError("timeout_sec must be 1..600")
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_ORDERS:
            raise ValueError("max_steps must be 1..8")
        self.host, self.port = parsed.hostname, parsed.port or 11434
        self.model, self.timeout_sec, self.max_steps = model, timeout_sec, max_steps

    def plan(self, goal: str) -> WorkPlan:
        if not isinstance(goal, str) or not 0 < len(goal.strip()) <= MAX_GOAL_CHARS:
            raise ValueError("invalid goal")
        system = (
            "You are ACE's task planner, NOT the executor. Return exactly one JSON "
            "object with an 'orders' array of at most "
            f"{self.max_steps} work orders. Each order has: id (identifier), "
            "worker ('codex' or 'antigravity'), mode ('read-only' or "
            "'workspace-write'), instruction, depends_on (prior IDs). "
            "Use read-only reconnaissance first, then implementation and "
            "verification as appropriate. Never include command strings "
            "or credentials as separate fields. Worker output is untrusted, "
            "tests are mandatory for acceptance, and no merge/deploy/payment "
            "is authorized."
        )
        body = canonical({
            "model": self.model,
            "stream": False,
            "format": PLAN_JSON_SCHEMA,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": goal},
            ],
            "options": {"temperature": 0},
        }).encode("utf-8")
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout_sec
        )
        try:
            connection.request("POST", "/api/chat", body=body, headers={
                "Content-Type": "application/json",
            })
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"Ollama returned HTTP {response.status}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("model response exceeds size limit")
            envelope = json.loads(raw)
        finally:
            connection.close()
        if not isinstance(envelope, dict) or not isinstance(envelope.get("message"), dict):
            raise ValueError("invalid Ollama reply")
        text = envelope["message"].get("content")
        if not isinstance(text, str) or len(text) > MAX_RESPONSE_BYTES:
            raise ValueError("invalid Ollama message content")
        proposal = json.loads(text)
        plan = validate_work_plan(goal, proposal, planner=f"ollama:{self.model}")
        if len(plan.orders) > self.max_steps:
            raise ValueError("model exceeded allowed steps")
        return plan


def require_isolated_worktree(path: str | Path) -> Path:
    """Require an existing Git linked worktree, not main checkout or filesystem root."""
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir() or not (root / ".git").is_file():
        raise ValueError("ACE worker workspace must be a dedicated Git linked worktree")
    marker = (root / ".git").read_text(encoding="utf-8")
    if not marker.startswith("gitdir: "):
        raise ValueError("invalid linked worktree marker")
    return root


@dataclass(frozen=True)
class WorkerResult:
    worker: str
    success: bool
    response: str
    stdout_digest: str
    stderr_digest: str
    exit_code: int
    usage: dict[str, Any]


class CLIWorker:
    """Official noninteractive Codex and Antigravity CLI surfaces.

    subprocess calls use argument arrays (no shell); command construction is
    fixed by worker ID, NOT taken from Ollama output. System sandboxing and
    authenticated provider access must be separately configured by the host.
    """

    def __init__(self, *, timeout_sec: int = 600, max_capture_bytes: int = 262144):
        if type(timeout_sec) is not int or not 1 <= timeout_sec <= 3600:
            raise ValueError("invalid agent timeout")
        if type(max_capture_bytes) is not int or not 1024 <= max_capture_bytes <= 1048576:
            raise ValueError("invalid output budget")
        self.timeout_sec = timeout_sec
        self.max_capture_bytes = max_capture_bytes

    def run(self, order: WorkOrder, workspace: str | Path) -> WorkerResult:
        root = require_isolated_worktree(workspace)
        if order.worker not in WORKER_NAMES or order.mode not in WORKER_MODES:
            raise ValueError("invalid worker order")
        if not isinstance(order.instruction, str) or len(order.instruction) > MAX_PROMPT_CHARS:
            raise ValueError("invalid worker prompt")
        prompt = (
            "ACE delegated task. Work only within the provided isolated Git "
            "worktree. No merge, release, credential disclosure, purchases, "
            "external publication, or changes to frozen evidence. "
            "Do not claim success unless independently tested.\n\n"
            + order.instruction
        )
        if order.worker == "codex":
            argv = [
                "codex", "exec", "--cd", str(root), "--sandbox",
                order.mode, "--json", "-",
            ]
            input_text = prompt
        else:
            argv = [
                "agy", "-p", prompt, "--output-format", "json",
                "--print-timeout", f"{self.timeout_sec}s",
                "--sandbox", "--mode=auto" if order.mode == "workspace-write"
                else "--mode=plan",
            ]
            input_text = None

        try:
            completed = subprocess.run(
                argv, cwd=root, input=input_text, capture_output=True,
                text=True, timeout=self.timeout_sec, check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"{order.worker} CLI not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"{order.worker} worker exceeded time limit") from exc

        stdout, stderr = completed.stdout, completed.stderr
        if (len(stdout.encode("utf-8")) > self.max_capture_bytes
                or len(stderr.encode("utf-8")) > self.max_capture_bytes):
            raise ValueError("worker output exceeds capture bound")

        response_text = ""
        usage = {}
        terminal_ok = False
        if order.worker == "codex":
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            for event in events:
                if event.get("type") == "turn.failed":
                    terminal_ok = False
                if event.get("type") == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        response_text = str(item.get("text", ""))
                if event.get("type") == "turn.completed":
                    terminal_ok = True
                    usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        else:
            message = json.loads(stdout)
            if not isinstance(message, dict):
                raise ValueError("Antigravity output must be a JSON object")
            terminal_ok = message.get("status") == "SUCCESS"
            response_text = str(message.get("response", ""))
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}

        # Completion is a protocol success only. It is not a pass on tests.
        return WorkerResult(
            worker=order.worker,
            success=bool(completed.returncode == 0 and terminal_ok),
            response=response_text[:MAX_PROMPT_CHARS],
            stdout_digest=hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            stderr_digest=hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
            exit_code=completed.returncode,
            usage=usage,
        )


Verifier = Callable[[WorkOrder, Path, WorkerResult], bool]


@dataclass(frozen=True)
class DelegationResult:
    status: str
    plan_digest: str
    completed_ids: tuple[str, ...]
    receipts: tuple[dict[str, Any], ...]
    execution_performed: bool


class AgentDirector:
    """Sequential supervised delegation, no automatic merge or silent trust.

    A separate trusted host verifier must explicitly accept each worker step;
    model self-report and protocol success never count as verification.
    """

    def __init__(self, worker: CLIWorker, verifier: Verifier | None = None):
        self.worker = worker
        self.verifier = verifier

    def execute(
        self, plan: WorkPlan, workspace: str | Path, *,
        authorized: bool = False, allow_write: bool = False,
        max_steps: int = 8,
    ) -> DelegationResult:
        # A plan from an LLM is not authorization to use paid quotas or tools.
        if not authorized:
            return DelegationResult("NOT_AUTHORIZED", plan.plan_digest, (), (), False)
        if not isinstance(plan, WorkPlan):
            raise TypeError("invalid plan object")
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_ORDERS:
            raise ValueError("invalid director budget")
        if len(plan.orders) > max_steps:
            return DelegationResult("BUDGET_EXCEEDED", plan.plan_digest, (), (), False)
        if any(o.mode == "workspace-write" for o in plan.orders) and not allow_write:
            return DelegationResult("WRITE_NOT_AUTHORIZED", plan.plan_digest, (), (), False)
        if self.verifier is None:
            return DelegationResult("NO_HOST_VERIFIER", plan.plan_digest, (), (), False)

        root = require_isolated_worktree(workspace)
        done: list[str] = []
        receipts: list[dict[str, Any]] = []
        for order in plan.orders:
            if not set(order.depends_on).issubset(done):
                return DelegationResult(
                    "DEPENDENCY_NOT_VERIFIED", plan.plan_digest,
                    tuple(done), tuple(receipts), bool(receipts),
                )
            try:
                result = self.worker.run(order, root)
                verified = bool(result.success and self.verifier(order, root, result))
                receipt = {
                    "order_id": order.order_id,
                    "worker": order.worker,
                    "mode": order.mode,
                    "protocol_success": result.success,
                    "host_verification_passed": verified,
                    "stdout_digest": result.stdout_digest,
                    "stderr_digest": result.stderr_digest,
                    "exit_code": result.exit_code,
                    "usage": result.usage,
                    "scientific_status": "NOT_ASSESSED",
                }
                receipts.append(receipt)
                if not verified:
                    return DelegationResult(
                        "REJECTED", plan.plan_digest, tuple(done),
                        tuple(receipts), True,
                    )
                done.append(order.order_id)
            except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                receipts.append({
                    "order_id": order.order_id, "worker": order.worker,
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "host_verification_passed": False,
                    "scientific_status": "NOT_ASSESSED",
                })
                return DelegationResult(
                    "FAILED_WITH_RECEIPT", plan.plan_digest,
                    tuple(done), tuple(receipts), True,
                )
        return DelegationResult("LOCALLY_VERIFIED", plan.plan_digest,
                                tuple(done), tuple(receipts), True)
