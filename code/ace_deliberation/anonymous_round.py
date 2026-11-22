"""Pisahkan hak memberikan suara dari transcript yang dibaca panel.

Token sesi dibentuk dalam memori dan terikat pada ID ronde. Keluaran publik
menyimpan ballot terstruktur tanpa identitas, token, urutan kedatangan atau
teks bebas. Bila kuorum privasi belum tercapai, ballot tetap dirahasiakan.
Katalog pilihan dan rujukan bersama ditetapkan sebelum menerima ballot.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets


MAX_MEMBERS = 500
MAX_ROOT_BYTES = 3_000_000
_LABEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,119}")
_TOKEN = re.compile(r"[a-f0-9]{64}")


class BallotError(ValueError):
    """Putaran anonim belum sah atau kredensial tidak dapat dipakai."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise BallotError("Field putaran anonim tidak sesuai skema.")


def _label(value):
    if not isinstance(value, str) or not _LABEL.fullmatch(value):
        raise BallotError("Label putaran harus berupa identifier terbatas.")
    return value


def _labels(values, low, high):
    if not isinstance(values, list) or not low <= len(values) <= high:
        raise BallotError("Jumlah label di luar batas.")
    cleaned = tuple(sorted(_label(value) for value in values))
    if len(set(cleaned)) != len(cleaned):
        raise BallotError("Label ganda.")
    return cleaned


def _encode(raw):
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(data):
    return hashlib.sha256(_encode(data)).hexdigest()


@dataclass(frozen=True, slots=True)
class AnonymousPlan:
    round_id: str
    members: tuple[str, ...]
    options: tuple[str, ...]
    allowed_refs: tuple[str, ...]
    quorum: int

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("round_id", "members", "options", "allowed_refs", "quorum"))
        members = _labels(raw["members"], 3, MAX_MEMBERS)
        options = _labels(raw["options"], 2, 30)
        refs = _labels(raw["allowed_refs"], 0, 200)
        quorum = raw["quorum"]
        if type(quorum) is not int or not 3 <= quorum <= len(members):
            raise BallotError("Kuorum privasi minimal tiga dan wajib tercakup roster.")
        identifier = _label(raw["round_id"])
        if set(members) & ({identifier} | set(options) | set(refs)):
            raise BallotError("Label publik tidak boleh memakai identifier anggota.")
        return cls(identifier, members, options, refs, quorum)

    def public_fields(self):
        return {"round_id": self.round_id, "options": list(self.options),
                "allowed_refs": list(self.allowed_refs), "quorum": self.quorum}


def _normalize_ballot(raw, options, allowed_refs):
    _shape(raw, ("option", "confidence", "refs"))
    option = _label(raw["option"])
    confidence = raw["confidence"]
    refs = _labels(raw["refs"], 0, 10)
    if option not in options or any(ref not in allowed_refs for ref in refs):
        raise BallotError("Ballot merujuk pilihan atau bukti di luar katalog.")
    if type(confidence) is not int or not 0 <= confidence <= 100:
        raise BallotError("Confidence wajib integer 0–100.")
    return {"option": option, "confidence": confidence, "refs": list(refs)}


class AnonymousRound:
    """Simpan roster dan kredensial privat hanya dalam instance sesi."""

    def __init__(self, plan, *, key=None):
        self.plan = AnonymousPlan.from_dict(plan)
        token_key = secrets.token_bytes(32) if key is None else key
        if not isinstance(token_key, bytes) or len(token_key) < 32:
            raise BallotError("Material token sesi belum cukup.")
        self._tokens = {
            member: hmac.digest(token_key, _encode([self.plan.round_id, member]), "sha256").hex()
            for member in self.plan.members
        }
        self._allowed_tokens = set(self._tokens.values())
        self._received = {}
        self._transcript = None

    def private_token(self, member):
        """Capai token hanya melalui pemanggil privat yang memegang roster."""
        member = _label(member)
        if self._transcript is not None or member not in self._tokens:
            raise BallotError("Token sesi tidak tersedia.")
        return self._tokens[member]

    def cast(self, token, ballot):
        if (self._transcript is not None or not isinstance(token, str) or not _TOKEN.fullmatch(token)
                or token not in self._allowed_tokens or token in self._received):
            raise BallotError("Ballot tidak dapat diterima.")
        self._received[token] = _normalize_ballot(ballot, self.plan.options, self.plan.allowed_refs)
        return True

    def progress(self):
        return {"phase": "closed" if self._transcript is not None else "collecting",
                "quorum_reached": self._transcript is not None or len(self._received) >= self.plan.quorum}

    def close(self):
        """Publikasikan transcript hanya setelah kuorum privasi tercapai."""
        if self._transcript is not None:
            return json.loads(self._transcript)
        if len(self._received) < self.plan.quorum:
            raise BallotError("Kuorum privasi belum tercapai.")
        base = {**self.plan.public_fields(), "schema": "ace.anonymous-round.v1",
                "ballots": sorted(self._received.values(), key=_encode)}
        self._transcript = _encode({**base, "sha256": _digest(base)})
        self._tokens.clear()
        self._allowed_tokens.clear()
        self._received.clear()
        return json.loads(self._transcript)


def verify_public(raw):
    """Verifikasi skema, kuorum, susunan kanonis, dan hash transcript publik."""
    try:
        keys = ("round_id", "options", "allowed_refs", "quorum", "schema", "ballots", "sha256")
        _shape(raw, keys)
        if raw["schema"] != "ace.anonymous-round.v1":
            return False
        _label(raw["round_id"])
        options = _labels(raw["options"], 2, 30)
        refs = _labels(raw["allowed_refs"], 0, 200)
        quorum, ballots = raw["quorum"], raw["ballots"]
        if (type(quorum) is not int or not isinstance(ballots, list)
                or not 3 <= quorum <= len(ballots) <= MAX_MEMBERS):
            return False
        normalized = [_normalize_ballot(item, options, refs) for item in ballots]
        base = {**raw, "options": list(options), "allowed_refs": list(refs),
                "ballots": sorted(normalized, key=_encode)}
        del base["sha256"]
        return {**base, "sha256": _digest(base)} == raw
    except (ValueError, RecursionError):
        return False


def tally(report):
    if not verify_public(report):
        raise BallotError("Transcript publik tidak sah.")
    counts = Counter(row["option"] for row in report["ballots"])
    return {option: counts[option] for option in report["options"]}


def simulate(raw, *, key=None):
    _shape(raw, ("plan", "votes"))
    session = AnonymousRound(raw["plan"], key=key)
    if not isinstance(raw["votes"], list) or len(raw["votes"]) > MAX_MEMBERS:
        raise BallotError("Daftar ballot melampaui batas.")
    for row in raw["votes"]:
        _shape(row, ("member", "ballot"))
        session.cast(session.private_token(row["member"]), row["ballot"])
    return session.close()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            payload = stream.read(MAX_ROOT_BYTES + 1)
        if len(payload) > MAX_ROOT_BYTES:
            raise BallotError("Berkas putaran melampaui batas.")
        data = json.loads(payload)
        if args.verify:
            valid = verify_public(data)
            print(json.dumps({"valid": valid}))
            return int(not valid)
        print(json.dumps(simulate(data), indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
