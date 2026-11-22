"""Ekstrak prosodi dari sampel audio yang mengizinkan penggunaan gaya.

Analisis menyimpan pitch kelompok, jeda, dan energi. Pitch dibulatkan
sebelum mengarahkan sintesis suara generik. Sampel sumber dan ciri
identitas pembicara tidak menjadi bagian WAV hasil.
"""
import argparse
from hashlib import sha256
from math import isqrt
from pathlib import Path
from statistics import median_low
import sys

from . import voice_generator
from ._audio import MAX_WAV,mono,parse_wav
from ._contracts import ContractError,canonical,checked,decode,digest,identity,integer,obj,read,schema,text


def _pitch(window,rate):
    half=len(window)//2
    stride=2 if rate>=16000 else 1
    center=sum(window)//len(window)
    measures=[]
    for lag in range(max(1,rate//330),min(half,rate//75)+1):
        one=[window[index]-center for index in range(0,len(window)-lag,stride)]
        two=[window[index+lag]-center for index in range(0,len(window)-lag,stride)]
        a=sum(value*value for value in one)
        b=sum(value*value for value in two)
        norm=isqrt(a*b)
        product=sum(x*y for x,y in zip(one,two,strict=True))
        score=product*1000//norm if norm and product>0 else 0
        measures.append((lag,score))
    if len(measures)<3:
        return None
    threshold=max(700,max(score for _,score in measures)*9//10)
    peaks=[lag for index,(lag,score) in enumerate(measures[1:-1],1)
           if score>=threshold and score>=measures[index-1][1] and score>=measures[index+1][1]]
    return (rate+peaks[0]//2)//peaks[0] if peaks else None


def analyze(data,policy,expected):
    checked(policy,expected)
    schema(policy,"ace.media.voice-style-policy.v1",("source_ref","sample_sha256","sample_ref","permission",
                                                    "minimum_windows","silence_floor"))
    source=text(policy["source_ref"],"Sumber kebijakan suara")
    pointer=text(policy["sample_ref"],"Rujukan sampel")
    authorization=obj(policy["permission"],("purpose","reference"))
    if authorization["purpose"]!="prosody_reuse":
        raise ContractError("Izin eksplisit prosody_reuse diperlukan.")
    permission=text(authorization["reference"],"Rujukan izin")
    proof=digest(policy["sample_sha256"])
    if not isinstance(data,bytes) or sha256(data).hexdigest()!=proof:
        raise ContractError("Sampel suara tidak cocok dengan anchor.")
    audio=mono(parse_wav(data))
    if not audio.rate//4<=audio.frames<=audio.rate*12:
        raise ContractError("Panjang sampel gaya perlu 0,25–12 detik.")
    minimum=integer(policy["minimum_windows"],"Window bersuara minimum",3,250)
    silence_floor=integer(policy["silence_floor"],"Batas energi hening",25,10_000)
    width=audio.rate*45//1000
    counts=0
    paused=0
    amplitudes=[]
    pitches=[]
    for start in range(0,audio.frames-width+1,width):
        row=audio.samples[start:start+width]
        rms=isqrt(sum(sample*sample for sample in row)//width)
        counts+=1
        if rms<silence_floor:
            paused+=1
            continue
        amplitudes.append(rms)
        f0=_pitch(row,audio.rate)
        if f0 is not None:
            pitches.append(f0)
    pause_bp=paused*10_000//counts
    complete=len(pitches)>=minimum
    pitch=median_low(pitches) if complete else None
    suggest={
        "pitch_hz":max(85,min(260,(pitch+5)//10*10)),
        "speed_milli":max(720,min(1350,1100-pause_bp//20)),
        "peak":max(8000,min(18_000,median_low(amplitudes)*2)),
    } if complete else None
    return {"schema":"ace.media.voice-style-receipt.v1","policy_sha256":expected,"sample_sha256":proof,
            "source_ref":source,"sample_ref":pointer,"permission_ref":permission,"windows":counts,
            "pitched_windows":len(pitches),"pause_bp":pause_bp,"median_pitch_hz":pitch,
            "status":"prosody_measured" if complete else "insufficient_voiced_windows","generic_voice_settings":suggest}


def render(sample,policy,expected,narration,narration_anchor):
    checked(narration,narration_anchor)
    schema(narration,"ace.media.prosody-render-plan.v1",("source_ref","text","rate","seed"))
    proof=analyze(sample,policy,expected)
    settings=proof["generic_voice_settings"]
    result={"schema":"ace.media.prosody-render-receipt.v1","plan_sha256":narration_anchor,"analysis":proof,"voice":None}
    if settings is None:
        return None,{**result,"status":"held"}
    recipe={"schema":"ace.media.voice-plan.v1","source_ref":narration["source_ref"],"text":narration["text"],
            "language":"id","rate":narration["rate"],"seed":narration["seed"],**settings}
    data,receipt=voice_generator.synthesize(recipe,identity(recipe))
    return data,{**result,"voice":receipt,"status":"rendered_generic_prosody"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=analyze(read(args.audio,MAX_WAV),decode(read(args.policy)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="prosody_measured")


if __name__=="__main__":
    raise SystemExit(main())
