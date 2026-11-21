"""Dekode WAV PCM lokal dengan batas ukuran dan representasi stabil."""
from array import array
from dataclasses import dataclass
from io import BytesIO
import sys
import wave


MAX_BYTES = 20_000_000
MAX_SAMPLES = 3_000_000
MAX_RATE = 48_000
MIN_RATE = 8000


@dataclass(frozen=True, slots=True)
class Audio:
    sample_rate: int
    channels: int
    sample_count: int
    mono: array


def decode(payload):
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise ValueError("Ukuran WAV melampaui batas.")
    try:
        with wave.open(BytesIO(payload), "rb") as audio:
            channels = audio.getnchannels()
            rate = audio.getframerate()
            width = audio.getsampwidth()
            count = audio.getnframes()
            if (channels not in (1, 2) or width not in (1, 2) or audio.getcomptype() != "NONE"
                    or not MIN_RATE <= rate <= MAX_RATE or not 1 <= count <= MAX_SAMPLES):
                raise ValueError("WAV perlu PCM 8/16-bit mono atau stereo dengan dimensi terbatas.")
            data = audio.readframes(count)
    except (EOFError, wave.Error) as exc:
        raise ValueError("Header WAV tidak sah.") from exc
    if len(data) != count*channels*width:
        raise ValueError("WAV terpotong sebelum semua sampel terbaca.")
    if width == 1:
        values = array("h", ((value-128)*256 for value in data))
    else:
        values = array("h")
        values.frombytes(data)
        if sys.byteorder != "little":
            values.byteswap()
    mono = values if channels == 1 else array("h", ((left+right)//2 for left, right in zip(values[::2], values[1::2])))
    return Audio(rate, channels, count, mono)
