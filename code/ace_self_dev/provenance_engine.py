"""Provenance Engine: Cryptographic provenance and execution authentication for ACE V0.2.

Eliminates embedded hardcoded signing secrets in source code.
Authenticates candidate generation via:
1. Dynamic environment secret (ACE_SIGNING_KEY) or ephemeral cryptographic token (secrets.token_hex).
2. Trusted process runtime metadata (PID, platform, Python runtime, git commit SHA).
3. HMAC-SHA256 signature verification over candidate source digest and execution context.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time
from typing import Optional, Tuple

from .models import AuthorType, ProvenanceProof


def _resolve_git_sha() -> str:
    """Resolve current Git HEAD SHA reliably without external dependencies."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )
        return res.stdout.strip()
    except Exception:
        # Fallback reading .git directly
        try:
            head_path = Path(".git/HEAD")
            if head_path.exists():
                content = head_path.read_text(encoding="utf-8").strip()
                if content.startswith("ref: "):
                    ref_path = Path(".git") / content[5:]
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()
                return content
        except Exception:
            pass
        return "UNKNOWN_COMMIT_SHA"


class ProvenanceEngine:
    """Generates and verifies cryptographic execution provenance proofs."""

    def __init__(self, signing_key: Optional[str] = None):
        # Eliminate hardcoded keys: read from env or generate cryptographically secure token
        if signing_key:
            self._key = signing_key
        elif "ACE_SIGNING_KEY" in os.environ and os.environ["ACE_SIGNING_KEY"].strip():
            self._key = os.environ["ACE_SIGNING_KEY"].strip()
        else:
            # Ephemeral 256-bit cryptographic token per session
            self._key = secrets.token_hex(32)

        self._key_fingerprint = hashlib.sha256(self._key.encode("utf-8")).hexdigest()[:16]
        self._cached_git_sha = _resolve_git_sha()

    @property
    def key_fingerprint(self) -> str:
        return self._key_fingerprint

    @property
    def signing_key(self) -> str:
        return self._key

    def create_provenance_proof(
        self,
        source_sha: str,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
    ) -> ProvenanceProof:
        """Create a verifiable cryptographic provenance proof from execution runtime context."""
        pid = os.getpid()
        plat = f"{platform.system()} {platform.machine()}"
        py_ver = sys.version.split()[0]
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Construct deterministic signing payload
        payload = f"{author_type.value}:{pid}:{plat}:{py_ver}:{self._cached_git_sha}:{source_sha}:{timestamp}".encode("utf-8")
        sig = hmac.new(self._key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        return ProvenanceProof(
            author_type=author_type,
            execution_pid=pid,
            platform=plat,
            python_version=py_ver,
            git_commit_sha=self._cached_git_sha,
            source_sha=source_sha,
            key_fingerprint=self._key_fingerprint,
            hmac_signature=sig,
            timestamp=timestamp,
        )

    def verify_provenance_proof(self, proof: ProvenanceProof) -> Tuple[bool, str]:
        """Verify an execution provenance proof against the signing key."""
        if proof.key_fingerprint != self._key_fingerprint:
            return False, f"Key fingerprint mismatch (expected {self._key_fingerprint}, got {proof.key_fingerprint})"

        payload = (
            f"{proof.author_type.value}:{proof.execution_pid}:{proof.platform}:"
            f"{proof.python_version}:{proof.git_commit_sha}:{proof.source_sha}:{proof.timestamp}"
        ).encode("utf-8")
        expected_sig = hmac.new(self._key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(proof.hmac_signature, expected_sig):
            return False, "HMAC signature verification failed"

        return True, "Provenance signature verified successfully"
