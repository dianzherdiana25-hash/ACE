"""Host-isolated Credential & Browser Profile Vault for ACE v3.

Design invariants (Zero Secret Leakage):
1. All credentials & browser session profiles live under `<workspace>/vault/`
   with restrictive POSIX permissions (`0700` dirs, `0600` files).
2. Secret values MUST NEVER appear in AI prompts, MCP tool outputs,
   cognitive memory, store events, work orders, or git diffs.
3. Redaction & leak-detection helpers here are shared across git_ops,
   agent_director, portable_dispatch, and web relay.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any


_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bEAAG[A-Za-z0-9]{16,}\b"),  # Meta Graph / Page access tokens
    re.compile(r"\bEAA[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),  # GitHub tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{25,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?KEY-----"),
)

_SENSITIVE_KEY_NAMES = frozenset({
    "access_token",
    "page_access_token",
    "fb_page_token",
    "fb_page_access_token",
    "ace_fb_page_token",
    "cookie",
    "cookies",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "api_key",
    "bearer",
    "authorization",
    "x-ace-token",
    "ace_web_token",
    "ace_mcp_http_token",
})


def contains_secret_pattern(text: str) -> str | None:
    """Return a generic pattern label if `text` looks like it contains a raw credential, else None."""
    if not isinstance(text, str) or not text:
        return None
    for idx, pat in enumerate(_SECRET_VALUE_PATTERNS):
        if pat.search(text):
            return f"secret_pattern_{idx}"
    return None


def redact_secrets(value: Any, *, extra_secrets: tuple[str, ...] = ()) -> Any:
    """Recursively scrub credential strings & sensitive keys from dicts/lists/strings."""
    if isinstance(value, str):
        out = value
        for pat in _SECRET_VALUE_PATTERNS:
            out = pat.sub("[REDACTED_SECRET]", out)
        for sec in extra_secrets:
            if sec and len(sec) >= 6 and sec in out:
                out = out.replace(sec, "[REDACTED_SECRET]")
        return out
    if isinstance(value, list):
        return [redact_secrets(v, extra_secrets=extra_secrets) for v in value]
    if isinstance(value, tuple):
        return [redact_secrets(v, extra_secrets=extra_secrets) for v in value]
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for k, v in value.items():
            if str(k).strip().lower() in _SENSITIVE_KEY_NAMES:
                cleaned[k] = "[REDACTED_SECRET]" if v else ""
            else:
                cleaned[k] = redact_secrets(v, extra_secrets=extra_secrets)
        return cleaned
    return value


class SecretVault:
    """Manages host-local secrets and persistent Chromium user-data profiles outside AI visibility."""

    SUPPORTED_VENUES = ("facebook", "kbm", "github")

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()
        self.vault_dir = self.workspace / "vault"
        self.secrets_file = self.vault_dir / "credentials.json"
        self.profiles_dir = self.vault_dir / "browser_profiles"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        for venue in self.SUPPORTED_VENUES:
            (self.profiles_dir / venue).mkdir(parents=True, exist_ok=True)
        self._harden_mode(self.vault_dir, 0o700)
        self._harden_mode(self.profiles_dir, 0o700)

    @staticmethod
    def _harden_mode(path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass

    def _load_all(self) -> dict[str, dict[str, Any]]:
        if not self.secrets_file.is_file():
            return {}
        try:
            data = json.loads(self.secrets_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_all(self, data: dict[str, dict[str, Any]]) -> None:
        self._ensure_layout()
        tmp = self.secrets_file.with_name(self.secrets_file.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._harden_mode(tmp, 0o600)
        os.replace(tmp, self.secrets_file)
        self._harden_mode(self.secrets_file, 0o600)

    def browser_profile_dir(self, venue: str) -> Path:
        key = str(venue).strip().lower()
        if not key or not re.fullmatch(r"[a-z0-9_-]{2,40}", key):
            raise ValueError(f"Nama venue profil tidak valid: {venue!r}")
        p = self.profiles_dir / key
        p.mkdir(parents=True, exist_ok=True)
        self._harden_mode(p, 0o700)
        return p

    def set_venue_credentials(self, venue: str, values: dict[str, Any]) -> dict[str, Any]:
        """Persist credentials for a venue (`facebook`, `kbm`, etc.) without returning secret values."""
        key = str(venue).strip().lower()
        if not key or not re.fullmatch(r"[a-z0-9_-]{2,40}", key):
            raise ValueError(f"Nama venue tidak valid: {venue!r}")
        if not isinstance(values, dict):
            raise ValueError("values harus berupa objek")
        data = self._load_all()
        cur = dict(data.get(key) or {})
        for k, v in values.items():
            if v is not None:
                cur[str(k)] = v
        data[key] = cur
        self._save_all(data)
        return self.venue_status(key)

    def get_venue_credentials(self, venue: str) -> dict[str, Any]:
        """Trusted host-executor-only read. Never expose returned dict to AI tools or logs."""
        key = str(venue).strip().lower()
        data = self._load_all()
        cur = dict(data.get(key) or {})
        if key == "facebook":
            env_pid = os.environ.get("ACE_FB_PAGE_ID", "").strip()
            env_tok = os.environ.get("ACE_FB_PAGE_TOKEN", "").strip()
            if env_pid and not cur.get("page_id"):
                cur["page_id"] = env_pid
            if env_tok and not cur.get("page_access_token"):
                cur["page_access_token"] = env_tok
        return cur

    def has_browser_profile_session(self, venue: str) -> bool:
        p = self.browser_profile_dir(venue)
        markers = [
            p / "Default" / "Cookies",
            p / "Default" / "Network" / "Cookies",
            p / "Local State",
            p / "session_ready.json",
        ]
        return any(m.exists() for m in markers)

    def mark_browser_session_ready(self, venue: str, *, account_label: str = "") -> dict[str, Any]:
        p = self.browser_profile_dir(venue)
        marker = p / "session_ready.json"
        marker.write_text(
            json.dumps({"venue": venue, "account_label": account_label, "ready": True}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._harden_mode(marker, 0o600)
        return self.venue_status(venue)

    def secret_values(self) -> tuple[str, ...]:
        """Return known non-empty secret strings solely for scrubbing logs/prompts."""
        data = self._load_all()
        found: list[str] = []
        for entry in data.values():
            if isinstance(entry, dict):
                for k, v in entry.items():
                    if isinstance(v, str) and len(v) >= 8 and (
                        k.lower() in _SENSITIVE_KEY_NAMES or "token" in k.lower() or "cookie" in k.lower() or "secret" in k.lower()
                    ):
                        found.append(v)
        for env_k in ("ACE_FB_PAGE_TOKEN", "ACE_WEB_TOKEN", "ACE_MCP_HTTP_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            val = os.environ.get(env_k, "").strip()
            if len(val) >= 8:
                found.append(val)
        return tuple(dict.fromkeys(found))

    def venue_status(self, venue: str) -> dict[str, Any]:
        key = str(venue).strip().lower()
        creds = self.get_venue_credentials(key)
        configured_keys = sorted(k for k, v in creds.items() if bool(v))
        profile_ready = self.has_browser_profile_session(key)
        return {
            "venue": key,
            "configured_fields": configured_keys,
            "has_api_credentials": bool(creds.get("page_access_token") and creds.get("page_id"))
            if key == "facebook"
            else bool(configured_keys),
            "browser_profile_dir": str(self.browser_profile_dir(key)),
            "browser_session_present": profile_ready,
            "ready": bool(profile_ready or configured_keys),
        }

    def all_status(self) -> dict[str, Any]:
        return {
            "vault_dir": str(self.vault_dir),
            "venues": {v: self.venue_status(v) for v in self.SUPPORTED_VENUES},
        }
