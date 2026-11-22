"""PCM16 WAV dan resampling integer untuk rantai studio lokal."""
from array import array
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import sys
import wave

from ._contracts import ContractError,integer


MAX_WAV=24_000_000
MAX_SAMPLES=10_000_000
RATES={8000,12000,16000,22050,24000,32000,44100,48000}


def sample_rate(value):
    if type(value) is not int or value not in RATES:
        raise ContractError("Sample rate WAV tidak didukung.")
    return value


def clamp(value):
    return max(-32768,min(32767,value))


def pcm_bytes(samples):
    data=array("h",samples)
    if sys.byteorder!="little":
        data.byteswap()
    return data.tobytes()


@dataclass(frozen=True)
class Audio:
    rate:int
    channels:int
    samples:tuple

    def __post_init__(self):
        sample_rate(self.rate)
        integer(self.channels,"Kanal",1,2)
        if not isinstance(self.samples,tuple) or not len(self.samples)<=MAX_SAMPLES or len(self.samples)%self.channels:
            raise ContractError("Batas atau bentuk PCM tidak sah.")

    @property
    def frames(self):
        return len(self.samples)//self.channels

    def receipt(self):
        return {"sample_rate":self.rate,"channels":self.channels,"frames":self.frames,
                "duration_ms":self.frames*1000//self.rate,"peak":max(map(abs,self.samples),default=0),
                "pcm_sha256":sha256(pcm_bytes(self.samples)).hexdigest()}


def wav(audio):
    stream=BytesIO()
    try:
        with wave.open(stream,"wb") as header:
            header.setnchannels(audio.channels)
            header.setsampwidth(2)
            header.setframerate(audio.rate)
            header.writeframes(pcm_bytes(audio.samples))
        return stream.getvalue()
    finally:
        stream.close()


def parse_wav(data):
    if not isinstance(data,bytes) or len(data)>MAX_WAV:
        raise ContractError("WAV melampaui batas.")
    try:
        with wave.open(BytesIO(data),"rb") as track:
            rate=sample_rate(track.getframerate())
            channels=integer(track.getnchannels(),"Kanal",1,2)
            count=track.getnframes()
            if not 0<=count<=MAX_SAMPLES//channels or track.getsampwidth()!=2 or track.getcomptype()!="NONE":
                raise ContractError("WAV harus PCM16 mono atau stereo dalam batas.")
            payload=track.readframes(count)
            if len(payload)!=2*channels*count:
                raise ContractError("Panjang PCM berbeda dari header.")
    except (wave.Error,EOFError) as error:
        raise ContractError("Header WAV tidak sah.") from error
    samples=array("h")
    samples.frombytes(payload)
    if sys.byteorder!="little":
        samples.byteswap()
    return Audio(rate,channels,tuple(samples))


def silence(rate,channels,frames):
    sample_rate(rate)
    integer(channels,"Kanal",1,2)
    integer(frames,"Frame",0,MAX_SAMPLES//channels)
    return Audio(rate,channels,(0,)*(frames*channels))


def mono(audio):
    if audio.channels==1:
        return audio
    return Audio(audio.rate,1,tuple((left+right)//2 for left,right in zip(audio.samples[::2],audio.samples[1::2],strict=True)))


def align(audio,rate,channels):
    sample_rate(rate)
    integer(channels,"Kanal",1,2)
    if not audio.frames:
        return Audio(rate,channels,())
    if channels==1:
        audio=mono(audio)
    frames=(audio.frames*rate+audio.rate//2)//audio.rate
    if frames*channels>MAX_SAMPLES:
        raise ContractError("Batas resampling audio terlampaui.")
    destination=[]
    for index in range(frames):
        base,ratio=divmod(index*audio.rate,rate)
        base=min(base,audio.frames-1)
        following=min(base+1,audio.frames-1)
        for channel in range(channels):
            position=min(channel,audio.channels-1)
            low=audio.samples[audio.channels*base+position]
            high=audio.samples[audio.channels*following+position]
            destination.append((low*(rate-ratio)+high*ratio+rate//2)//rate)
    return Audio(rate,channels,tuple(destination))
