"""Rakit kanal suara lokal dua arah dari rekaman PCM yang bertambat ke turn dialog."""
import argparse
from hashlib import sha256
import hmac
from io import BytesIO
from pathlib import Path
import socket
from struct import Struct
from threading import Lock
import sys
import wave

from ._contracts import (
    PresenceError, anchor, canonical, decode, identifier, integer, items, obj, read, schema, source_bytes, text,
)
from ._journal import load_export


def _wav(raw):
    try:
        with wave.open(BytesIO(raw), "rb") as channel:
            rate = channel.getframerate()
            frames = channel.getnframes()
            if channel.getnchannels() != 1 or channel.getsampwidth() != 2 or not 8000 <= rate <= 48000:
                raise PresenceError("Kanal suara perlu WAV PCM16 mono dan sample rate 8–48 kHz.")
            if not 0 < frames <= rate * 30:
                raise PresenceError("Setiap segmen suara perlu lebih dari nol dan maksimal 30 detik.")
            data = channel.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise PresenceError("Segmen WAV tidak dapat dibaca.") from error
    if len(data) != frames * 2 or not any(data):
        raise PresenceError("Segmen kosong, hening atau tidak lengkap.")
    return rate, frames, data


def render_voice_exchange(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.duplex-plan.v1", ("dialogue", "clips", "pause_ms", "max_duration_ms"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    chain = load_export(source_bytes(root, ref["path"], ref["sha256"], 2_000_000))
    pauses = integer(plan["pause_ms"], "Jeda pergantian giliran", 0, 1000)
    cap = integer(plan["max_duration_ms"], "Durasi maksimum", 1000, 120000)
    input_ = {}
    for clip in items(plan["clips"], 160, 2):
        obj(clip, ("id", "turn_sha256", "path", "sha256", "permission_ref"))
        key = identifier(clip["id"], "Turn suara")
        if key in input_:
            raise PresenceError("Setiap turn suara punya satu klip.")
        input_[key] = clip
    observed = {item["turn"]["id"] for item in chain["events"]}
    if input_.keys() != observed:
        raise PresenceError("Klip suara harus mencakup turn yang sama dengan jurnal.")
    rate = None
    channels = bytearray()
    offset = 0
    timeline = []
    for item in chain["events"]:
        row = item["turn"]
        key = row["id"]
        indexed = input_[key]
        grant = text(indexed["permission_ref"], "Izin klip suara")
        if item["sha256"] != indexed["turn_sha256"]:
            raise PresenceError("Audio tidak tertambat pada hash turn yang ditunjuk.")
        content = source_bytes(root, indexed["path"], indexed["sha256"], 3_000_000)
        source_rate, span, sound = _wav(content)
        if rate is None:
            rate = source_rate
        if rate != source_rate:
            raise PresenceError("Semua klip harus memakai sample rate sama.")
        silent = rate * pauses // 1000 if timeline else 0
        if (offset + silent + span) * 1000 > cap * rate:
            raise PresenceError("Timeline audio melampaui anggaran.")
        channels.extend(b"\0\0\0\0" * silent)
        offset += silent
        destination = 0 if row["role"] == "user" else 1
        if destination == 0:
            interleaved = b"".join(sound[index:index + 2] + b"\0\0" for index in range(0, len(sound), 2))
        else:
            interleaved = b"".join(b"\0\0" + sound[index:index + 2] for index in range(0, len(sound), 2))
        channels.extend(interleaved)
        timeline.append({"id": key, "role": row["role"], "channel": destination, "samples": [offset, offset + span],
                         "turn_sha256": indexed["turn_sha256"], "source_audio_sha256": indexed["sha256"], "permission_ref": grant})
        offset += span
    with BytesIO() as output:
        with wave.open(output, "wb") as stream:
            stream.setparams((2, 2, rate, 0, "NONE", "not compressed"))
            stream.writeframes(channels)
        sound = output.getvalue()
    return sound, {"schema": "ace.presence.duplex-recording.v1", "plan_sha256": expected, "session": chain["session"],
                   "dialogue_head_sha256": chain["head_sha256"], "output_sha256": sha256(sound).hexdigest(),
                   "sample_rate": rate, "frames": offset, "timeline": timeline, "mode": "authorized_input_recordings"}


_WIRE = Struct("!4sBBII")
_MAGIC = b"AP59"
_MAC_SIZE = sha256().digest_size
_ROLES = ("user", "assistant")
_AUDIO, _END = 1, 2
_PACKET_LIMIT = 1200


def _read_exact(stream, size):
    data = bytearray(size)
    view = memoryview(data)
    offset = 0
    while offset < size:
        received = stream.recv_into(view[offset:])
        if not received:
            raise PresenceError("Kanal PCM ditutup sebelum terminator yang utuh.")
        offset += received
    return bytes(data)


def _grant(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.live-voice.v1", ("session", "rate", "max_block_ms", "max_stream_ms", "roles"))
    identifier(plan["session"], "Sesi suara")
    rate = integer(plan["rate"], "Sample rate", 8000, 48000)
    block = integer(plan["max_block_ms"], "Batas blok milidetik", 10, 500)
    total = integer(plan["max_stream_ms"], "Batas sesi milidetik", block, 120_000)
    roles = obj(plan["roles"], _ROLES)
    return rate, rate * block // 1000, rate * total // 1000, {
        role: text(roles[role], "Referensi izin kanal", 300) for role in _ROLES
    }


class PCMChannel:
    """Endpoint PCM16 mono bidirectional pada socket lokal yang telah dipasangkan.

    Pemanggil memasok klip PCM lewat send_audio dan menerima frame lewat
    receive. Finish menyegel arah kirim saja sehingga lawan bicara masih
    dapat membalas. Audio dan kunci tetap di memori proses.
    """

    def __init__(self, stream, role, config, proof, key):
        if stream.family != socket.AF_UNIX:
            raise PresenceError("Endpoint suara hanya menerima socket AF_UNIX.")
        self._stream = stream
        self._role = role
        self._rate, self._frame_limit, self._total_limit, self._roles = config
        self._proof = bytes.fromhex(proof)
        self._key = key
        self._send_lock, self._read_lock = Lock(), Lock()
        self._counts = {"sending": {"packets": 0, "frames": 0}, "receiving": {"packets": 0, "frames": 0}}
        self._ended = {"sending": False, "receiving": False}
        self._broken = False

    @property
    def role(self):
        return _ROLES[self._role]

    def _ensure_open(self, direction):
        if self._broken or self._stream.fileno() < 0:
            raise PresenceError("Kanal audio sudah ditutup.")
        if self._ended[direction]:
            raise PresenceError("Arah kanal audio sudah disegel.")

    def _authenticate(self, header, payload):
        return hmac.digest(self._key, self._proof + header + payload, "sha256")

    def _expected_seq(self, direction):
        return self._counts[direction]["packets"] + 1

    def _envelope(self, direction, role, kind, count, sequence):
        if kind not in (_AUDIO, _END) or sequence != self._expected_seq(direction) or sequence > _PACKET_LIMIT:
            raise PresenceError("Nomor urut atau jenis paket PCM tidak sah.")
        seen = self._counts[direction]["frames"]
        if kind == _END and count != 0:
            raise PresenceError("Terminator audio tidak boleh memuat sample.")
        if kind == _AUDIO and (not 0 < count <= self._frame_limit or seen + count > self._total_limit
                               or sequence == _PACKET_LIMIT):
            raise PresenceError("Paket PCM melebihi batas frame atau anggaran sesi.")
        return _WIRE.pack(_MAGIC, role, kind, sequence, count)

    def _receipt(self, direction, kind, sequence, role, payload):
        count = len(payload) // 2
        captured = self._counts[direction]
        first = captured["frames"]
        captured["frames"] += count
        captured["packets"] += 1
        self._ended[direction] = kind == _END
        return {"role": _ROLES[role], "seq": sequence, "end": kind == _END,
                "samples": [first, first + count], "sample_rate": self._rate,
                "pcm_sha256": sha256(payload).hexdigest(), "permission_ref": self._roles[_ROLES[role]]}

    def _transport_failure(self, error):
        self._broken = True
        self.close()
        if isinstance(error, PresenceError):
            raise error
        raise PresenceError("Transport PCM lokal tidak dapat melanjutkan frame.") from error

    def _write(self, kind, payload):
        with self._send_lock:
            self._ensure_open("sending")
            index = self._expected_seq("sending")
            header = self._envelope("sending", self._role, kind, len(payload) // 2, index)
            try:
                self._stream.sendall(header + payload + self._authenticate(header, payload))
                if kind == _END:
                    self._stream.shutdown(socket.SHUT_WR)
            except OSError as error:
                self._transport_failure(error)
            return self._receipt("sending", kind, index, self._role, payload)

    def send_audio(self, payload):
        if type(payload) is not bytes or not payload or len(payload) % 2:
            raise PresenceError("Paket harus bytes PCM16 mono dengan jumlah byte genap.")
        return self._write(_AUDIO, payload)

    def finish(self):
        return self._write(_END, b"")

    def receive(self):
        with self._read_lock:
            self._ensure_open("receiving")
            try:
                header = _read_exact(self._stream, _WIRE.size)
                magic, sender, packet_type, index, count = _WIRE.unpack(header)
                if magic != _MAGIC or sender != 1 - self._role:
                    raise PresenceError("Paket PCM bukan dari arah dan protokol yang disepakati.")
                self._envelope("receiving", sender, packet_type, count, index)
                payload = _read_exact(self._stream, count * 2)
                mac = _read_exact(self._stream, _MAC_SIZE)
                if not hmac.compare_digest(mac, self._authenticate(header, payload)):
                    raise PresenceError("Autentikasi frame PCM tidak cocok.")
                return payload, self._receipt("receiving", packet_type, index, sender, payload)
            except (OSError, PresenceError) as error:
                self._transport_failure(error)

    def capture_wave(self):
        """Tampung arah terima sebagai WAV setelah frame akhir terautentikasi."""
        receipts = []
        with BytesIO() as data:
            with wave.open(data, "wb") as output:
                output.setparams((1, 2, self._rate, 0, "NONE", "PCM16 mono"))
                while True:
                    payload, receipt = self.receive()
                    receipts.append(receipt)
                    if receipt["end"]:
                        break
                    output.writeframesraw(payload)
            wav = data.getvalue()
        sample_sum = sum(item["samples"][1] - item["samples"][0] for item in receipts)
        return wav, {
            "role": _ROLES[1 - self._role],
            "sample_rate": self._rate,
            "frames": sample_sum,
            "wav_sha256": sha256(wav).hexdigest(),
            "packet_receipts": receipts,
        }

    def close(self):
        if self._stream.fileno() >= 0:
            try:
                self._stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def open_duplex(plan, expected, session_key, *, timeout_seconds=4):
    """Buat sepasang endpoint lokal tanpa mengambil mikrofon dan tanpa membukukan audio."""
    config = _grant(plan, expected)
    if type(session_key) is not bytes or len(session_key) != 32:
        raise PresenceError("Kanal PCM memerlukan kunci sesi 32 byte yang hanya tersimpan di memori.")
    if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= 30:
        raise PresenceError("Timeout kanal PCM di luar batas.")
    user, assistant = socket.socketpair()
    try:
        user.settimeout(timeout_seconds)
        assistant.settimeout(timeout_seconds)
        return PCMChannel(user, 0, config, expected, session_key), PCMChannel(assistant, 1, config, expected, session_key)
    except (OSError, ValueError):
        user.close()
        assistant.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    cfg = parser.parse_args(argv)
    try:
        audio, receipt = render_voice_exchange(decode(read(cfg.plan)), cfg.expect_sha256, cfg.root)
        with cfg.output.open("xb") as stream:
            stream.write(audio)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
